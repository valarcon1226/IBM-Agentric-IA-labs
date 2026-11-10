"""Resilience test: Crash fault tolerance (Connect worker and Source PG restarts).

Validates that crashes cause at-least-once redelivery, never data loss,
and that idempotent upserts absorb all duplicates resulting in 0 differences.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time

import httpx
import pytest
from qa_common import MetricsRecorder, assert_target

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    wait_for_cdc_pipeline_idle,
)
from tools.reconcile import reconcile_ledger
from tools.workload import WorkloadGenerator

logger = logging.getLogger("test_crash")

CONNECT_URL = "http://127.0.0.1:8083"


def wait_for_connect_running(timeout: float = 60.0) -> None:
    """Wait until Kafka Connect REST API and all connectors are RUNNING."""
    start = time.monotonic()
    client = httpx.Client(base_url=CONNECT_URL, timeout=10.0)
    try:
        while time.monotonic() - start < timeout:
            try:
                r_src = client.get("/connectors/postgres-source/status")
                r_snk = client.get("/connectors/jdbc-sink/status")
                if r_src.status_code == 200 and r_snk.status_code == 200:
                    src_state = r_src.json().get("connector", {}).get("state")
                    snk_state = r_snk.json().get("connector", {}).get("state")
                    src_tasks = r_src.json().get("tasks", [])
                    snk_tasks = r_snk.json().get("tasks", [])

                    src_ok = (
                        src_state == "RUNNING"
                        and bool(src_tasks)
                        and all(t.get("state") == "RUNNING" for t in src_tasks)
                    )
                    snk_ok = (
                        snk_state == "RUNNING"
                        and bool(snk_tasks)
                        and all(t.get("state") == "RUNNING" for t in snk_tasks)
                    )

                    if src_ok and snk_ok:
                        logger.info("Both postgres-source and jdbc-sink are RUNNING.")
                        return
            except Exception:
                pass
            time.sleep(2.0)
    finally:
        client.close()

    raise TimeoutError(f"Connectors did not return to RUNNING within {timeout}s after restart")


def get_sink_committed_offset() -> int:
    """Get current committed offset of connect-jdbc-sink."""
    for _ in range(5):
        try:
            res = subprocess.run(
                ["docker", "exec", "cdc-redpanda", "rpk", "group", "describe", "connect-jdbc-sink"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            for line in res.stdout.splitlines():
                if "cdc.public.ledger" in line:
                    parts = line.split()
                    if len(parts) >= 3 and parts[2].isdigit():
                        return int(parts[2])
        except Exception:
            pass
        time.sleep(1.0)
    return 0


def get_topic_log_end_offset(topic: str = "cdc.public.ledger") -> int:
    """Get current log end offset of the topic from Redpanda."""
    try:
        res = subprocess.run(
            ["docker", "exec", "cdc-redpanda", "rpk", "group", "describe", "connect-jdbc-sink"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        for line in res.stdout.splitlines():
            if topic in line:
                parts = line.split()
                if len(parts) >= 6 and parts[4].isdigit():
                    return int(parts[4])
        return 0
    except Exception:
        return 0


@pytest.mark.resilience
@pytest.mark.req("REQ-CDC-004")
def test_crash_connect_worker_redelivery(metrics: MetricsRecorder) -> None:
    """Test A: docker kill Connect mid-stream at 500 rows/s.

    Asserts that connectors restart cleanly, redeliveries are absorbed, and 0 diffs remain.
    """
    target_rate = 500.0
    workload_duration = 90.0
    kill_at_seconds = 60.0

    start_id = int(time.time() * 100)
    generator = WorkloadGenerator(
        db_url=DEFAULT_SOURCE_URL,
        seed=201,
        target_rate=target_rate,
        initial_id=start_id,
    )

    offset_before_test = get_sink_committed_offset()
    logger.info("Initial sink committed offset: %d", offset_before_test)

    workload_thread = threading.Thread(
        target=lambda: generator.run(duration_seconds=workload_duration),
        daemon=True,
    )
    workload_thread.start()

    logger.info("Running workload for %.0f seconds before crash...", kill_at_seconds)
    time.sleep(kill_at_seconds)

    # Record offset before killing container
    offset_before_kill = get_sink_committed_offset()
    log_end_before_kill = get_topic_log_end_offset()
    logger.info(
        "Offsets before kill: committed=%d, log_end=%d",
        offset_before_kill,
        log_end_before_kill,
    )

    # 1. Abruptly kill Connect container
    logger.info("Executing 'docker kill cdc-connect'...")
    subprocess.run(["docker", "kill", "cdc-connect"], check=True)

    # Pause 5s while container is dead
    time.sleep(5.0)

    # 2. Restart Connect container
    logger.info("Executing 'docker start cdc-connect'...")
    subprocess.run(["docker", "start", "cdc-connect"], check=True)

    # 3. Wait for RUNNING state
    logger.info("Waiting for Connect to recover to RUNNING state...")
    wait_for_connect_running(timeout=60.0)

    # Let workload thread complete
    workload_thread.join(timeout=40.0)
    logger.info(
        "Workload completed: %d total operations written to source.",
        generator.stats.total_ops,
    )

    # Wait until CDC pipeline is completely idle
    logger.info("Waiting for CDC pipeline to become fully idle...")
    wait_for_cdc_pipeline_idle(timeout=120.0)

    offset_after_recovery = get_sink_committed_offset()
    total_events_streamed = offset_after_recovery - offset_before_test
    # Uncommitted batches in flight during kill are re-fetched and re-applied
    redeliveries_absorbed = max(
        0, total_events_streamed - (generator.stats.inserts + generator.stats.updates)
    )
    logger.info(
        "Offset delta: %d, Ops: %d. Redeliveries absorbed by sink: %d",
        total_events_streamed,
        generator.stats.total_ops,
        redeliveries_absorbed,
    )

    # Record redeliveries metric
    metrics.record("redeliveries_absorbed_connect_kill", float(redeliveries_absorbed))

    # Reconcile tables: 0 differences
    logger.info("Reconciling tables post Connect kill...")
    rec_result = reconcile_ledger(chunk_size=10_000)
    assert rec_result.total_differences == 0, (
        f"Reconciler found {rec_result.total_differences} differences "
        f"(missing={len(rec_result.missing_keys)}, extra={len(rec_result.extra_keys)}, "
        f"changed={len(rec_result.changed_keys)})"
    )
    assert_target("rows_differ_after_fault", rec_result.total_differences)


@pytest.mark.resilience
@pytest.mark.req("REQ-CDC-004")
def test_crash_source_postgres_recovery(metrics: MetricsRecorder) -> None:
    """Test B: Restart source PostgreSQL mid-workload.

    Asserts that replication slot and decoding resume without data loss.
    """
    target_rate = 500.0
    workload_duration = 50.0
    restart_at_seconds = 20.0

    start_id = int(time.time() * 100)
    generator = WorkloadGenerator(
        db_url=DEFAULT_SOURCE_URL,
        seed=301,
        target_rate=target_rate,
        initial_id=start_id,
    )

    workload_thread = threading.Thread(
        target=lambda: generator.run(duration_seconds=workload_duration),
        daemon=True,
    )
    workload_thread.start()

    logger.info("Workload running for %.0f seconds before source restart...", restart_at_seconds)
    time.sleep(restart_at_seconds)

    # Restart source postgres container
    logger.info("Restarting 'cdc-postgres-source' mid-workload...")
    subprocess.run(["docker", "restart", "cdc-postgres-source"], check=True)

    # Wait for postgres-source to become healthy
    time.sleep(5.0)
    logger.info("Waiting for source PostgreSQL container to become ready...")
    cmd_isready = [
        "docker", "exec", "cdc-postgres-source",
        "pg_isready", "-U", "postgres", "-d", "source_db",
    ]
    for _ in range(20):
        res = subprocess.run(cmd_isready, capture_output=True)
        if res.returncode == 0:
            logger.info("Source PostgreSQL is ready.")
            break
        time.sleep(1.0)

    # Let workload thread complete
    workload_thread.join(timeout=40.0)
    logger.info("Workload finished. Total ops: %d", generator.stats.total_ops)

    # Wait for connect to resume and drain lag
    logger.info("Waiting for CDC pipeline to become fully idle...")
    wait_for_cdc_pipeline_idle(timeout=120.0)

    # Reconcile tables: 0 differences
    logger.info("Reconciling tables post source Postgres restart...")
    rec_result = reconcile_ledger(chunk_size=10_000)
    assert rec_result.total_differences == 0, (
        f"Reconciler found {rec_result.total_differences} differences "
        f"(missing={len(rec_result.missing_keys)}, extra={len(rec_result.extra_keys)}, "
        f"changed={len(rec_result.changed_keys)})"
    )
    assert_target("rows_differ_after_fault", rec_result.total_differences)
