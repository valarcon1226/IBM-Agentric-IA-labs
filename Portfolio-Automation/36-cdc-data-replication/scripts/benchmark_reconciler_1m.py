"""Benchmark reconciler performance on 1,000,000 identical rows.

Verifies target: Reconciler time for 1M rows <= 120s.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from tools.reconcile import (  # noqa: E402
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    reconcile_ledger,
)
from tools.workload import preload_ledger_rows  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_1m")

CONNECT_URL = "http://127.0.0.1:8083"


def pause_connectors() -> None:
    try:
        with httpx.Client(base_url=CONNECT_URL, timeout=10.0) as client:
            client.put("/connectors/postgres-source/pause")
            client.put("/connectors/jdbc-sink/pause")
        logger.info("Paused Debezium connectors for clean snapshot benchmark.")
    except Exception as exc:
        logger.warning("Could not pause connectors: %s", exc)


def resume_connectors() -> None:
    try:
        with httpx.Client(base_url=CONNECT_URL, timeout=10.0) as client:
            client.put("/connectors/postgres-source/resume")
            client.put("/connectors/jdbc-sink/resume")
        logger.info("Resumed Debezium connectors.")
    except Exception as exc:
        logger.warning("Could not resume connectors: %s", exc)


def run_1m_benchmark() -> float:
    pause_connectors()
    try:
        logger.info("Resetting ledger tables for 1M row benchmark...")
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            with s_conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE ledger;")
        with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
            with w_conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE ledger;")

        total_rows = 1_000_000
        batch_size = 50_000

        logger.info("Preloading %d identical rows into source database...", total_rows)
        t_preload_s = preload_ledger_rows(
            DEFAULT_SOURCE_URL,
            total_rows=total_rows,
            batch_size=batch_size,
            start_id=1,
            seed=12345,
        )

        logger.info("Preloading %d identical rows into warehouse database...", total_rows)
        t_preload_w = preload_ledger_rows(
            DEFAULT_WAREHOUSE_URL,
            total_rows=total_rows,
            batch_size=batch_size,
            start_id=1,
            seed=12345,
        )
        logger.info(
            "Preloading complete: source=%.2fs, warehouse=%.2fs",
            t_preload_s,
            t_preload_w,
        )

        logger.info("Starting reconciliation of %d rows (target <= 120.0s)...", total_rows)
        result = reconcile_ledger(
            source_url=DEFAULT_SOURCE_URL,
            warehouse_url=DEFAULT_WAREHOUSE_URL,
            chunk_size=10_000,
        )
        elapsed = result.elapsed_seconds

        logger.info(
            "1M Reconciliation finished in %.2f s (Source=%d, Warehouse=%d, Matched=%d, Diffs=%d)",
            elapsed,
            result.total_source_rows,
            result.total_warehouse_rows,
            result.matched_keys,
            result.total_differences,
        )

        assert result.total_differences == 0, (
            f"Expected 0 differences, got {result.total_differences}"
        )
        msg = f"Expected {total_rows} matches, got {result.matched_keys}"
        assert result.matched_keys == total_rows, msg
        assert elapsed <= 120.0, f"Reconciler took {elapsed:.2f}s, exceeding 120s target"

        print("\n==========================================")
        print(f"1M_RECONCILE_PASSED: {elapsed:.2f}s (target <= 120.0s)")
        print(f"Matched rows: {result.matched_keys}")
        print(f"Differences: {result.total_differences}")
        print("==========================================\n")
        return elapsed
    finally:
        resume_connectors()


def main() -> None:
    try:
        run_1m_benchmark()
    except Exception as exc:
        logger.error("1M Benchmark failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
