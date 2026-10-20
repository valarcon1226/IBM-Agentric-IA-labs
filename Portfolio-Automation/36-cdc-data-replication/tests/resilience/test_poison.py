"""Resilience test: Poison pill row isolation and Dead Letter Queue (DLQ) verification."""

from __future__ import annotations

import decimal
import logging
import time
from typing import Any

import httpx
import psycopg
import pytest
from confluent_kafka import Consumer, Producer

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    wait_for_cdc_pipeline_idle,
)

logger = logging.getLogger("test_poison")
CONNECT_URL = "http://127.0.0.1:8083"
KAFKA_BOOTSTRAP = "127.0.0.1:9092"
TOPIC_SOURCE = "cdc.public.ledger"
TOPIC_DLQ = "dlq_ledger"


@pytest.mark.resilience
@pytest.mark.req("REQ-CDC-005")
def test_poison_row_isolation_and_dlq() -> None:
    """Verify that poison pill records are safely isolated to the DLQ while valid rows flow.

    Scenario:
    1. 1,000 valid business records are inserted into the source PostgreSQL table.
    2. 3 malformed poison pill records are injected into the replication topic.
    3. Asserts:
       - 1,000 valid rows successfully replicate and reach the warehouse table.
       - DLQ topic ('dlq_ledger') holds exactly 3 records matching the poison keys.
       - DLQ headers carry full Kafka Connect error diagnostics (__connect.errors.*).
       - Kafka Connect JDBC sink connector remains in RUNNING state.

    Architecture Note (Finding DBZ-7877):
    Kafka Connect's built-in DLQ mechanism intercepts converter and transformation errors
    seamlessly at the framework level. For database-level constraint violations (e.g. stricter
    CHECK constraints in warehouse), Debezium JDBC Sink 2.7.3 does not implement KIP-610
    ErrantRecordReporter, causing task failure rather than DLQ routing.
    """
    base_id = int(time.time() * 1000)
    total_valid_rows = 1000

    # 1. Prepare 1,000 valid business rows
    valid_rows: list[tuple[int, str, decimal.Decimal, str, str]] = [
        (
            base_id + i,
            f"acc_valid_{base_id + i}",
            decimal.Decimal("150.00"),
            "USD",
            "NEW",
        )
        for i in range(total_valid_rows)
    ]

    logger.info("Inserting %d valid records into source database...", total_valid_rows)
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        with s_conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ledger (
                    id, account_id, amount, currency, status, created_at, source_commit_ts
                ) VALUES (%s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp());
                """,
                valid_rows,
            )

    # 2. Inject 3 poison pills directly into the replication topic
    poison_producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})
    poison_keys = [f"poison_key_{base_id}_{i}".encode("utf-8") for i in range(3)]

    logger.info("Injecting 3 poison pill messages into topic '%s'...", TOPIC_SOURCE)
    for pk in poison_keys:
        poison_producer.produce(
            topic=TOPIC_SOURCE,
            key=pk,
            value=b"MALFORMED_NON_JSON_POISON_PILL_RECORD",
        )
    poison_producer.flush(timeout=10.0)

    # 3. Wait for CDC pipeline to process valid rows and route poison pills
    logger.info("Awaiting CDC pipeline to process batch and isolate poison rows...")
    wait_for_cdc_pipeline_idle(timeout=60.0)

    # 4. Assert all 1,000 valid records arrived in warehouse
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM ledger WHERE id >= %s AND id < %s;",
                (base_id, base_id + total_valid_rows),
            )
            row = cur.fetchone()
            assert row is not None
            warehouse_count = row[0]

    logger.info(
        "Warehouse verification: arrived=%d (expected %d)",
        warehouse_count,
        total_valid_rows,
    )
    assert warehouse_count == total_valid_rows, (
        f"Expected {total_valid_rows} rows in warehouse, got {warehouse_count}"
    )

    # 5. Read DLQ topic with confluent-kafka (pinned)
    logger.info("Reading DLQ topic '%s' with confluent-kafka...", TOPIC_DLQ)
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": f"dlq-verifier-{base_id}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([TOPIC_DLQ])

    matched_dlq_records: list[dict[str, Any]] = []
    poll_start = time.monotonic()

    while time.monotonic() - poll_start < 25.0 and len(matched_dlq_records) < 3:
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error():
            continue

        if msg.key() in poison_keys:
            raw_headers = msg.headers() or []
            headers: dict[str, str] = {}
            for h_item in raw_headers:
                hk: str = str(h_item[0])
                hv: Any = h_item[1]
                if isinstance(hv, bytes):
                    headers[hk] = hv.decode("utf-8", errors="replace")
                else:
                    headers[hk] = str(hv)

            matched_dlq_records.append(
                {
                    "key": msg.key(),
                    "value": msg.value(),
                    "headers": headers,
                    "offset": msg.offset(),
                    "partition": msg.partition(),
                }
            )

    consumer.close()

    logger.info("Found %d matched poison records in DLQ.", len(matched_dlq_records))
    assert len(matched_dlq_records) == 3, (
        f"Expected 3 poison records in DLQ matching {poison_keys}, got {len(matched_dlq_records)}"
    )

    # 6. Verify exact Kafka Connect DLQ diagnostic headers (Kafka Connect 3.7 / Debezium 2.7.3)
    for rec in matched_dlq_records:
        h = rec["headers"]
        logger.info("DLQ record key=%s headers: %s", rec["key"], list(h.keys()))

        # Cited Kafka Connect DLQ headers:
        assert h.get("__connect.errors.topic") == TOPIC_SOURCE
        assert "__connect.errors.partition" in h
        assert "__connect.errors.offset" in h
        assert h.get("__connect.errors.connector.name") == "jdbc-sink"
        assert h.get("__connect.errors.task.id") == "0"
        assert h.get("__connect.errors.stage") in (
            "KEY_CONVERTER",
            "VALUE_CONVERTER",
            "TRANSFORMATION",
        )
        assert h.get("__connect.errors.class.name") == "org.apache.kafka.connect.json.JsonConverter"
        assert (
            h.get("__connect.errors.exception.class.name")
            == "org.apache.kafka.connect.errors.DataException"
        )
        assert "Converting byte[] to Kafka Connect data failed" in h.get(
            "__connect.errors.exception.message", ""
        )
        assert "__connect.errors.exception.stacktrace" in h

    # 7. Assert connector remains in RUNNING state
    with httpx.Client(base_url=CONNECT_URL, timeout=10.0) as client:
        resp = client.get("/connectors/jdbc-sink/status")
        assert resp.status_code == 200
        status_data = resp.json()
        assert status_data.get("connector", {}).get("state") == "RUNNING"
        tasks = status_data.get("tasks", [])
        assert bool(tasks)
        assert all(t.get("state") == "RUNNING" for t in tasks)

    logger.info("Poison test passed: 1000 in warehouse, 3 in DLQ, connector is RUNNING.")
