"""Smoke test: Ingests 10,000 rows against the real CDC stack and reconciles.

Used in the PR Gate CI workflow to verify end-to-end pipeline health.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    wait_for_cdc_pipeline_idle,
)
from tools.reconcile import reconcile_ledger
from tools.workload import preload_ledger_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smoke_10k")


def run_smoke_10k(
    source_url: str = DEFAULT_SOURCE_URL,
    warehouse_url: str = DEFAULT_WAREHOUSE_URL,
    timeout: float = 90.0,
) -> float:
    """Preload 10,000 rows into source, await replication in warehouse, and reconcile."""
    start_time = time.monotonic()
    start_id = int(time.time() * 1000)
    total_rows = 10_000

    # 1. Get baseline warehouse row count
    with psycopg.connect(warehouse_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ledger;")
            row = cur.fetchone()
            wh_baseline = int(row[0]) if row else 0

    target_wh_count = wh_baseline + total_rows
    logger.info(
        "Starting 10k smoke test: baseline warehouse rows=%d, target=%d, start_id=%d",
        wh_baseline,
        target_wh_count,
        start_id,
    )

    # 2. Bulk preload 10,000 rows into source
    t_load_start = time.monotonic()
    preload_ledger_rows(
        source_url,
        total_rows=total_rows,
        batch_size=5_000,
        start_id=start_id,
        seed=1001,
    )
    load_duration = time.monotonic() - t_load_start
    logger.info("Inserted %d rows into source in %.2f s.", total_rows, load_duration)

    # 3. Wait for warehouse count to reach target
    logger.info("Awaiting replication of 10,000 rows to warehouse (timeout=%.1fs)...", timeout)
    t_poll_start = time.monotonic()
    wh_count = 0
    while time.monotonic() - t_poll_start < timeout:
        with psycopg.connect(warehouse_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM ledger;")
                row = cur.fetchone()
                wh_count = int(row[0]) if row else 0

        if wh_count >= target_wh_count:
            break
        time.sleep(1.0)

    assert wh_count >= target_wh_count, (
        f"Replication timeout: expected >= {target_wh_count} rows in warehouse, got {wh_count}"
    )

    # 4. Wait for idle and reconcile
    wait_for_cdc_pipeline_idle(timeout=60.0)
    rep_duration = time.monotonic() - t_load_start
    logger.info("Replication of 10,000 rows completed in %.2f s.", rep_duration)

    # 5. Keyset reconcile the 10,000 row segment
    logger.info(
        "Reconciling 10,000 row smoke batch (id %d to %d)...",
        start_id,
        start_id + total_rows - 1,
    )
    rec = reconcile_ledger(
        source_url=source_url,
        warehouse_url=warehouse_url,
        min_id=start_id,
        max_id=start_id + total_rows - 1,
    )

    logger.info(
        "Reconcile: Source=%d, Warehouse=%d, Matched=%d, Diffs=%d (Time=%.2fs)",
        rec.total_source_rows,
        rec.total_warehouse_rows,
        rec.matched_keys,
        rec.total_differences,
        rec.elapsed_seconds,
    )

    assert rec.is_clean, f"Reconciliation differences found: {rec.total_differences}"
    assert rec.total_source_rows == total_rows
    assert rec.total_warehouse_rows == total_rows
    assert rec.total_differences == 0

    total_elapsed = time.monotonic() - start_time
    logger.info("=== 10k Smoke Test PASSED in %.2f s ===", total_elapsed)
    return total_elapsed


def main() -> None:
    try:
        duration = run_smoke_10k()
        print(f"SMOKE_10K_PASSED: {duration:.2f}s")
    except Exception as exc:
        logger.error("10k Smoke test failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
