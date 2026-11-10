"""Register or update Debezium connectors via Kafka Connect REST API."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import httpx
import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("register")

SOURCE_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/source_db"
WAREHOUSE_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5436/warehouse_db"
CONNECT_URL = "http://127.0.0.1:8083"
TOXIPROXY_URL = "http://127.0.0.1:8474"


def init_source_db() -> None:
    logger.info("Initializing source database schema...")
    with psycopg.connect(SOURCE_DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id BIGINT PRIMARY KEY,
                    account_id VARCHAR(64) NOT NULL,
                    amount NUMERIC(14, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                    source_commit_ts TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
                );
                ALTER TABLE ledger REPLICA IDENTITY FULL;
            """)
    logger.info("Source database initialized with REPLICA IDENTITY FULL.")


def init_warehouse_db() -> None:
    logger.info("Initializing warehouse database schema...")
    with psycopg.connect(WAREHOUSE_DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id BIGINT PRIMARY KEY,
                    account_id VARCHAR(64) NOT NULL,
                    amount NUMERIC(14, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                    source_commit_ts TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                    warehouse_arrival_ts TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
                );

                CREATE OR REPLACE FUNCTION set_warehouse_arrival()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.warehouse_arrival_ts = clock_timestamp();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trg_warehouse_arrival ON ledger;
                CREATE TRIGGER trg_warehouse_arrival
                BEFORE INSERT OR UPDATE ON ledger
                FOR EACH ROW EXECUTE FUNCTION set_warehouse_arrival();
            """)
    logger.info("Warehouse database initialized with arrival timestamp trigger.")


def ensure_toxiproxy() -> None:
    logger.info("Checking Toxiproxy configuration...")
    client = httpx.Client(base_url=TOXIPROXY_URL, timeout=10.0)
    try:
        resp = client.get("/proxies/warehouse_pg")
        if resp.status_code == 200:
            logger.info("Toxiproxy 'warehouse_pg' proxy already exists.")
            return
        payload = {
            "name": "warehouse_pg",
            "listen": "0.0.0.0:5432",
            "upstream": "postgres-warehouse:5432",
            "enabled": True,
        }
        create_resp = client.post("/proxies", json=payload)
        create_resp.raise_for_status()
        logger.info("Created Toxiproxy 'warehouse_pg' -> postgres-warehouse:5432.")
    except Exception as exc:
        logger.warning("Toxiproxy check/creation notice: %s", exc)
    finally:
        client.close()


def wait_for_connect(client: httpx.Client, timeout: float = 60.0) -> None:
    logger.info("Waiting for Kafka Connect REST API to be ready...")
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            resp = client.get("/connectors")
            if resp.status_code == 200:
                logger.info("Kafka Connect is ready.")
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise TimeoutError(f"Kafka Connect at {CONNECT_URL} was not ready within {timeout}s")


def register_connector(client: httpx.Client, config_path: Path) -> str:
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    name = data["name"]
    config = data["config"]
    logger.info("Registering connector '%s' from %s...", name, config_path.name)

    get_resp = client.get(f"/connectors/{name}")
    if get_resp.status_code == 200:
        logger.info("Connector '%s' exists, updating configuration...", name)
        put_resp = client.put(f"/connectors/{name}/config", json=config)
        put_resp.raise_for_status()
    else:
        logger.info("Creating connector '%s'...", name)
        post_resp = client.post("/connectors", json={"name": name, "config": config})
        if post_resp.status_code not in (200, 201, 409):
            post_resp.raise_for_status()

    return name


def wait_for_running(client: httpx.Client, connector_name: str, timeout: float = 60.0) -> None:
    logger.info("Waiting for connector '%s' to reach RUNNING state...", connector_name)
    start = time.monotonic()
    last_state = "UNKNOWN"
    while time.monotonic() - start < timeout:
        try:
            resp = client.get(f"/connectors/{connector_name}/status")
            if resp.status_code == 200:
                status_data = resp.json()
                c_state = status_data.get("connector", {}).get("state")
                tasks = status_data.get("tasks", [])
                last_state = f"connector={c_state}, tasks={[t.get('state') for t in tasks]}"

                is_c_running = c_state == "RUNNING"
                tasks_running = bool(tasks) and all(t.get("state") == "RUNNING" for t in tasks)
                if is_c_running and tasks_running:
                    logger.info(
                        "Connector '%s' and tasks are RUNNING! (%s)",
                        connector_name,
                        last_state,
                    )
                    return
                for t in tasks:
                    if t.get("state") == "FAILED":
                        trace = t.get("trace", "No trace")
                        raise RuntimeError(f"Task for '{connector_name}' FAILED: {trace}")
        except RuntimeError:
            raise
        except Exception:
            pass
        time.sleep(1.0)

    raise TimeoutError(
        f"Connector '{connector_name}' failed to reach RUNNING within {timeout}s "
        f"(last state: {last_state})"
    )


def main() -> None:
    init_source_db()
    init_warehouse_db()
    ensure_toxiproxy()

    connect_dir = Path(__file__).resolve().parent.parent / "connectors"
    source_cfg = connect_dir / "postgres-source.json"
    sink_cfg = connect_dir / "jdbc-sink.json"

    with httpx.Client(base_url=CONNECT_URL, timeout=30.0) as client:
        wait_for_connect(client)

        src_name = register_connector(client, source_cfg)
        wait_for_running(client, src_name)

        sink_name = register_connector(client, sink_cfg)
        wait_for_running(client, sink_name)

    logger.info("All connectors successfully registered and RUNNING!")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("Registration failed: %s", exc)
        sys.exit(1)
