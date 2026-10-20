"""Initial snapshot and connector upgrade tests (Prompt 9 / REQ-CDC-007).

Validates:
1. Snapshot test: Preload 1,000,000 rows into PostgreSQL source, register a new source
   connector with snapshot.mode=initial, measure snapshot duration and verify 0 lost/repeated rows.
2. Upgrade test: Run workload on Debezium N-1 (2.6.2.Final), record committed offsets,
   upgrade Connect image to N (2.7.3.Final), verify no re-snapshot, measure upgrade downtime,
   and reconcile to 0 differences.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    get_rpk_consumer_lag,
    wait_for_cdc_pipeline_idle,
)
from tools.reconcile import reconcile_ledger
from tools.workload import WorkloadGenerator

logger = logging.getLogger("test_snapshot_upgrade")

CONNECT_URL = "http://127.0.0.1:8083"
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "connectors"
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"
COMPOSE_DIR = Path(__file__).resolve().parent.parent.parent


def _wait_for_connect_ready(timeout: float = 60.0) -> None:
    """Wait until Kafka Connect REST API responds with 200."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            res = httpx.get(f"{CONNECT_URL}/connectors", timeout=2.0)
            if res.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise TimeoutError("Kafka Connect REST API did not become ready in time.")


def _wait_for_connector_running(name: str, timeout: float = 60.0) -> None:
    """Wait until a connector and all its tasks reach RUNNING state."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            res = httpx.get(f"{CONNECT_URL}/connectors/{name}/status", timeout=2.0)
            if res.status_code == 200:
                data = res.json()
                c_state = data.get("connector", {}).get("state")
                tasks = data.get("tasks", [])
                if c_state == "RUNNING" and tasks and all(
                    t.get("state") == "RUNNING" for t in tasks
                ):
                    return
        except Exception:
            pass
        time.sleep(1.0)
    raise TimeoutError(f"Connector '{name}' did not reach RUNNING within {timeout}s.")


def _register_connector_file(config_path: Path) -> None:
    """Register or update a connector configuration from file."""
    with open(config_path, encoding="utf-8") as f:
        payload = json.load(f)
    _register_connector_dict(payload)


def _register_connector_dict(payload: dict[str, Any]) -> None:
    """Register or update a connector configuration from dictionary."""
    name = payload["name"]
    config = payload["config"]

    res = httpx.get(f"{CONNECT_URL}/connectors/{name}", timeout=5.0)
    if res.status_code == 200:
        put_res = httpx.put(f"{CONNECT_URL}/connectors/{name}/config", json=config, timeout=10.0)
        put_res.raise_for_status()
    else:
        post_res = httpx.post(f"{CONNECT_URL}/connectors", json=payload, timeout=10.0)
        post_res.raise_for_status()

    _wait_for_connector_running(name)


def _delete_connector_if_exists(name: str) -> None:
    """Delete a connector if it exists."""
    try:
        res = httpx.delete(f"{CONNECT_URL}/connectors/{name}", timeout=10.0)
        if res.status_code in (200, 204):
            time.sleep(2.0)
    except Exception:
        pass


def _set_connect_version(version: str) -> None:
    """Switch Kafka Connect container image version via docker compose."""
    logger.info(
        "Switching Kafka Connect container image to quay.io/debezium/connect:%s...", version
    )
    env = os.environ.copy()
    env["DEBEZIUM_VERSION"] = version

    subprocess.run(
        ["docker", "compose", "stop", "connect"],
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "rm", "-f", "connect"],
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "up", "-d", "connect"],
        env=env,
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    _wait_for_connect_ready()


def _get_debezium_plugin_version() -> str:
    """Retrieve the deployed Debezium Postgres connector version from Kafka Connect."""
    res = httpx.get(f"{CONNECT_URL}/connector-plugins", timeout=5.0)
    res.raise_for_status()
    for p in res.json():
        if p["class"].endswith("PostgresConnector"):
            return str(p.get("version", "unknown"))
    return "unknown"


def _get_topic_end_offset(topic: str = "cdc.public.ledger") -> int:
    """Get the latest end offset for the specified topic from Redpanda."""
    proc = subprocess.run(
        ["docker", "exec", "cdc-redpanda", "rpk", "topic", "describe", topic, "-p"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] == "0" and parts[5].isdigit():
            return int(parts[5])
    return -1


@pytest.mark.migration
@pytest.mark.req("REQ-CDC-007")
def test_initial_snapshot_1m_rows() -> None:
    """Preload 1M rows, perform initial Debezium snapshot, and reconcile with 0 differences.

    Target metrics:
    - Rows lost or repeated in the initial snapshot of 1M rows: 0
    - Reconciler time for 1M rows: <= 120 s
    """
    logger.info("=== Starting Prompt 9 Part 1: Initial Snapshot of 1,000,000 Rows ===")

    # 1. Preload 1,000,000 rows into source database
    logger.info("Step 1: Preloading 1,000,000 rows into source_db.ledger...")
    t_preload_start = time.time()
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ledger;")
            cur.execute("""
                INSERT INTO ledger (
                    id, account_id, amount, currency, status, created_at, source_commit_ts
                )
                SELECT
                    g,
                    'acc_' || (g % 10000),
                    (10.00 + (g % 500))::numeric(14, 2),
                    CASE (g % 5)
                        WHEN 0 THEN 'USD'
                        WHEN 1 THEN 'EUR'
                        WHEN 2 THEN 'GBP'
                        WHEN 3 THEN 'JPY'
                        ELSE 'CAD'
                    END,
                    CASE (g % 5)
                        WHEN 0 THEN 'CONFIRMED'
                        WHEN 1 THEN 'SETTLED'
                        WHEN 2 THEN 'PENDING'
                        WHEN 3 THEN 'RECONCILED'
                        ELSE 'CANCELLED'
                    END,
                    clock_timestamp(),
                    clock_timestamp()
                FROM generate_series(1, 1000000) AS g;
            """)
    preload_time = round(time.time() - t_preload_start, 2)
    logger.info("Step 1 complete: Preloaded 1,000,000 rows in %.2f s.", preload_time)

    # 2. Reset warehouse table to 0 rows
    logger.info("Step 2: Truncating warehouse_db.ledger...")
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ledger;")

    # 3. Clean up any lingering snapshot connectors and slots
    logger.info("Step 3: Cleaning up prior snapshot connectors if present...")
    _delete_connector_if_exists("postgres-source-snap")
    _delete_connector_if_exists("jdbc-sink-snap")

    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pg_drop_replication_slot(slot_name)
                FROM pg_replication_slots
                WHERE slot_name = 'debezium_snap_slot';
            """)

    subprocess.run(
        ["docker", "exec", "cdc-redpanda", "rpk", "topic", "delete", "cdc_snap.public.ledger"],
        capture_output=True,
    )
    time.sleep(1.0)

    # 4. Define brand new source and sink connectors for the initial snapshot
    source_snap_config = {
        "name": "postgres-source-snap",
        "config": {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "tasks.max": "1",
            "plugin.name": "pgoutput",
            "database.hostname": "postgres-source",
            "database.port": "5432",
            "database.user": "postgres",
            "database.password": "postgres_password",
            "database.dbname": "source_db",
            "topic.prefix": "cdc_snap",
            "table.include.list": "public.ledger",
            "publication.autocreate.mode": "all_tables",
            "slot.name": "debezium_snap_slot",
            "snapshot.mode": "initial",
            "max.batch.size": "2048",
            "max.queue.size": "4096",
            "tombstones.on.delete": "true",
        },
    }

    sink_snap_config = {
        "name": "jdbc-sink-snap",
        "config": {
            "connector.class": "io.debezium.connector.jdbc.JdbcSinkConnector",
            "tasks.max": "1",
            "connection.url": "jdbc:postgresql://toxiproxy:5432/warehouse_db",
            "connection.username": "postgres",
            "connection.password": "postgres_password",
            "insert.mode": "upsert",
            "primary.key.mode": "record_key",
            "delete.enabled": "true",
            "schema.evolution": "basic",
            "topics": "cdc_snap.public.ledger",
            "table.name.format": "ledger",
            "batch.size": "5000",
            "internal.enable.sces": "true",
            "errors.tolerance": "all",
            "errors.deadletterqueue.topic.name": "dlq_ledger",
            "errors.deadletterqueue.topic.replication.factor": "1",
            "errors.deadletterqueue.context.headers.enable": "true",
        },
    }

    # 5. Register sink first, then register the new source connector with snapshot mode initial
    logger.info("Step 5: Registering 'jdbc-sink-snap' and 'postgres-source-snap'...")
    _register_connector_dict(sink_snap_config)

    t_snapshot_start = time.time()
    _register_connector_dict(source_snap_config)
    logger.info(
        "New source connector registered with snapshot.mode=initial. Ingesting 1M rows..."
    )

    # 6. Monitor progress until warehouse reaches 1,000,000 rows
    warehouse_count = 0
    poll_count = 0
    while time.time() - t_snapshot_start < 900.0:
        time.sleep(5.0)
        poll_count += 1
        with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM ledger;")
                row = cur.fetchone()
                warehouse_count = int(row[0]) if row else 0

        lag = get_rpk_consumer_lag("connect-jdbc-sink-snap")
        if poll_count % 3 == 0:
            logger.info(
                "Snapshot ingestion: %d / 1,000,000 rows in warehouse (%.1fs elapsed, lag=%d)",
                warehouse_count,
                time.time() - t_snapshot_start,
                lag,
            )

        if warehouse_count >= 1_000_000 and lag == 0:
            break

    assert warehouse_count == 1_000_000, (
        f"Expected 1,000,000 rows in warehouse, got {warehouse_count}"
    )

    snapshot_duration = round(time.time() - t_snapshot_start, 2)
    logger.info("=== Initial Snapshot & Replication Complete in %.2f s ===", snapshot_duration)

    # 7. Reconcile 1,000,000 rows
    logger.info("Step 7: Executing full keyset reconciliation on 1,000,000 rows...")
    rec = reconcile_ledger(chunk_size=10000)
    logger.info(
        "Reconcile: Source=%d, Warehouse=%d, Matched=%d, Diffs=%d (Time=%.2fs)",
        rec.total_source_rows,
        rec.total_warehouse_rows,
        rec.matched_keys,
        rec.total_differences,
        rec.elapsed_seconds,
    )

    # Assert targets
    assert rec.is_clean, f"Reconciliation differences found: {rec.total_differences}"
    assert rec.total_source_rows == 1_000_000
    assert rec.total_warehouse_rows == 1_000_000
    assert rec.total_differences == 0
    assert len(rec.missing_keys) == 0, f"Rows lost: {rec.missing_keys}"
    assert len(rec.extra_keys) == 0, f"Rows repeated/extra: {rec.extra_keys}"
    assert len(rec.changed_keys) == 0, f"Rows altered: {rec.changed_keys}"
    assert rec.elapsed_seconds <= 120.0, (
        f"Reconciliation exceeded target 120s: {rec.elapsed_seconds}s"
    )

    # Clean up snapshot connectors
    _delete_connector_if_exists("postgres-source-snap")
    _delete_connector_if_exists("jdbc-sink-snap")

    # Save metrics
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "snapshot_1m_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "preload_time_seconds": preload_time,
                "snapshot_duration_seconds": snapshot_duration,
                "reconciler_time_seconds": rec.elapsed_seconds,
                "total_rows": 1_000_000,
                "missing_rows": 0,
                "repeated_rows": 0,
                "differences": 0,
            },
            f,
            indent=2,
        )


@pytest.mark.migration
@pytest.mark.req("REQ-CDC-008")
def test_connector_upgrade_n_minus_1_to_n() -> None:
    """Run connector on Debezium N-1 (2.6.2.Final) under load, upgrade to N (2.7.3.Final),
    verify no re-snapshot, record upgrade downtime, and reconcile to 0 differences.
    """
    logger.info("=== Starting Prompt 9 Part 2: Connector Upgrade (N-1 -> N) ===")

    # 1. Switch Connect to N-1 (2.6.2.Final)
    _set_connect_version("2.6.2.Final")
    v_n_minus_1 = _get_debezium_plugin_version()
    logger.info("Active Debezium plugin version on Connect: %s", v_n_minus_1)
    assert "2.6.2" in v_n_minus_1, f"Expected 2.6.2, got {v_n_minus_1}"

    # Ensure connectors are registered and running on N-1
    _register_connector_file(CONFIG_DIR / "jdbc-sink.json")
    _register_connector_file(CONFIG_DIR / "postgres-source.json")
    wait_for_cdc_pipeline_idle(timeout=120.0)

    # 2. Start continuous workload under N-1
    base_id = int(time.time() * 1000)
    wg = WorkloadGenerator(DEFAULT_SOURCE_URL, target_rate=200.0, seed=301, initial_id=base_id)
    workload_thread = threading.Thread(target=wg.run, args=(12.0,), daemon=True)
    workload_thread.start()

    try:
        time.sleep(3.0)
        # 3. Record committed offset before upgrade
        pre_upgrade_offset = _get_topic_end_offset("cdc.public.ledger")
        logger.info("Pre-upgrade topic end offset: %d", pre_upgrade_offset)

        # 4. Perform upgrade to N (2.7.3.Final) while workload is writing to source
        logger.info("Performing online upgrade of Kafka Connect to Debezium N (2.7.3.Final)...")
        t_upgrade_start = time.time()
        _set_connect_version("2.7.3.Final")

        # Wait for connectors to resume RUNNING under N
        _wait_for_connector_running("postgres-source", timeout=60.0)
        _wait_for_connector_running("jdbc-sink", timeout=60.0)
        t_upgrade_end = time.time()
        upgrade_downtime = round(t_upgrade_end - t_upgrade_start, 2)
        logger.info("Connect upgrade to N complete! Upgrade downtime: %.2f s", upgrade_downtime)

        # 5. Verify upgraded version
        v_n = _get_debezium_plugin_version()
        logger.info("Post-upgrade Debezium plugin version: %s", v_n)
        assert "2.7.3" in v_n, f"Expected 2.7.3, got {v_n}"

        # 6. Let workload finish writing
        workload_thread.join(timeout=30.0)
        logger.info("Workload finished writing to PostgreSQL source.")

        # 7. Wait for post-upgrade offset to advance and assert no re-snapshot occurred
        start_wait = time.monotonic()
        post_upgrade_offset = pre_upgrade_offset
        while time.monotonic() - start_wait < 60.0:
            post_upgrade_offset = _get_topic_end_offset("cdc.public.ledger")
            if post_upgrade_offset > pre_upgrade_offset:
                break
            time.sleep(1.0)

        logger.info(
            "Post-upgrade topic end offset: %d (pre: %d)", post_upgrade_offset, pre_upgrade_offset
        )
        assert post_upgrade_offset > pre_upgrade_offset, (
            f"Offsets did not advance within 60s post-upgrade "
            f"(pre={pre_upgrade_offset}, post={post_upgrade_offset})"
        )
        # If a re-snapshot occurred, the offset would jump by 1,000,000+.
        # Ensure offset growth matches workload ops (~2,500)
        offset_delta = post_upgrade_offset - pre_upgrade_offset
        assert offset_delta < 50_000, (
            f"Offset jump {offset_delta} suggests an unexpected re-snapshot!"
        )

        # 8. Wait for pipeline idle under Debezium 2.7.3
        logger.info("Waiting for CDC pipeline to process all events and become idle...")
        wait_for_cdc_pipeline_idle(timeout=120.0)

        # 8. Reconcile all data
        logger.info("Step 8: Reconciling entire dataset post-upgrade...")
        rec = reconcile_ledger(chunk_size=10000)
        logger.info(
            "Upgrade Reconcile: Source=%d, Warehouse=%d, Matched=%d, Diffs=%d",
            rec.total_source_rows,
            rec.total_warehouse_rows,
            rec.matched_keys,
            rec.total_differences,
        )
        assert rec.is_clean, (
            f"Reconciliation found differences post-upgrade: {rec.total_differences}"
        )

        # Save metrics
        with open(RESULTS_DIR / "upgrade_metrics.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "from_version": v_n_minus_1,
                    "to_version": v_n,
                    "upgrade_downtime_seconds": upgrade_downtime,
                    "pre_upgrade_offset": pre_upgrade_offset,
                    "post_upgrade_offset": post_upgrade_offset,
                    "re-snapshot_occurred": False,
                    "total_rows_reconciled": rec.total_source_rows,
                    "differences": rec.total_differences,
                },
                f,
                indent=2,
            )

    finally:
        # Ensure Connect stays on N (2.7.3.Final)
        _set_connect_version("2.7.3.Final")
