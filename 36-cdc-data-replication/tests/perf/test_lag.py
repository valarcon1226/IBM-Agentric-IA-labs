"""Performance test: End-to-end replication lag across 100, 500, and 1,000 rows/s workloads."""

from __future__ import annotations

import logging
import threading
import time

import psycopg
import pytest
from qa_common import MetricsRecorder, assert_target

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    wait_for_consumer_lag_zero,
)
from tools.reconcile import reconcile_ledger
from tools.workload import WorkloadGenerator

logger = logging.getLogger("test_lag")


def sample_warehouse_lag(
    stop_event: threading.Event,
    metric_name: str,
    metrics: MetricsRecorder,
    start_id: int,
    sample_interval: float = 2.0,
) -> None:
    """Periodically queries warehouse for newly arrived rows and computes replication lag."""
    last_id = start_id
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            while not stop_event.is_set():
                cur.execute(
                    """
                    SELECT id,
                           EXTRACT(EPOCH FROM (warehouse_arrival_ts - source_commit_ts)) AS lag_s
                    FROM ledger
                    WHERE id > %s AND warehouse_arrival_ts IS NOT NULL
                    ORDER BY id ASC
                    LIMIT 200;
                    """,
                    (last_id,),
                )
                rows = cur.fetchall()
                if rows:
                    for r in rows:
                        _row_id, lag_sec = r[0], float(r[1])
                        # Normalize any sub-millisecond clock jitter
                        lag_sec = max(0.001, lag_sec)
                        metrics.record(metric_name, lag_sec)
                    last_id = rows[-1][0]
                time.sleep(sample_interval)


@pytest.mark.perf
@pytest.mark.req("REQ-CDC-002")
def test_replication_lag_under_load(metrics: MetricsRecorder) -> None:
    """Run workload at 100, 500, and 1,000 rows/s for 3 min each, recording p50, p95, p99."""
    rates = [100, 500, 1000]
    duration_per_rate = 180.0  # 3 minutes each, as specified in the plan

    base_id = int(time.time() * 100)

    for rate in rates:
        metric_name = f"lag_{rate}_rps"
        logger.info(
            "=== Starting workload at %d rows/s for %.0f seconds ===",
            rate,
            duration_per_rate,
        )
        start_id = base_id
        generator = WorkloadGenerator(
            db_url=DEFAULT_SOURCE_URL,
            seed=42 + rate,
            target_rate=float(rate),
            initial_id=start_id,
        )

        stop_sampler = threading.Event()
        sampler_thread = threading.Thread(
            target=sample_warehouse_lag,
            args=(stop_sampler, metric_name, metrics, start_id),
            daemon=True,
        )
        sampler_thread.start()

        # Run generator for exactly 3 minutes
        generator.run(duration_seconds=duration_per_rate)
        base_id = generator.next_id + 1000

        # Wait for sampler to drain trailing records
        time.sleep(3.0)
        stop_sampler.set()
        sampler_thread.join(timeout=5.0)

        # Wait until consumer lag is 0
        wait_for_consumer_lag_zero(timeout=60.0)

        computed = metrics.compute()
        summary = computed.get(metric_name, {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0})
        logger.info(
            "Rate %d rows/s complete: samples=%d, p50=%.3fs, p95=%.3fs, p99=%.3fs",
            rate,
            summary["count"],
            summary["p50"],
            summary["p95"],
            summary["p99"],
        )

        # Assert against targets.toml
        if rate == 500:
            assert_target("end_to_end_lag_p95_500_rps", summary["p95"])
        elif rate == 1000:
            assert_target("end_to_end_lag_p95_1000_rps", summary["p95"])

    # Reconcile at the end of the entire test
    logger.info("Reconciling tables after all rate stages...")
    rec_result = reconcile_ledger(chunk_size=10_000)
    assert rec_result.total_differences == 0, (
        f"Reconciler found {rec_result.total_differences} differences after perf test "
        f"(missing={len(rec_result.missing_keys)}, extra={len(rec_result.extra_keys)}, "
        f"changed={len(rec_result.changed_keys)})"
    )
    assert_target("rows_differ_after_fault", rec_result.total_differences)
