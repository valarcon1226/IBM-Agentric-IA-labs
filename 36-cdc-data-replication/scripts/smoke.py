"""Smoke test: Inserts one row in source and verifies it replicates to warehouse within 10s."""

from __future__ import annotations

import decimal
import logging
import sys
import time

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smoke")

SOURCE_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/source_db"
WAREHOUSE_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5436/warehouse_db"


def run_smoke_test(timeout: float = 10.0) -> float:
    # Unique ID using millisecond timestamp
    test_id = int(time.time() * 1000)
    test_account = f"acc_smoke_{test_id}"
    test_amount = decimal.Decimal("125.50")
    test_currency = "USD"
    test_status = "CONFIRMED"

    logger.info("Inserting smoke test row id=%d into source ledger...", test_id)
    with psycopg.connect(SOURCE_DB_URL, autocommit=True) as src_conn:
        with src_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ledger
                    (id, account_id, amount, currency, status, created_at, source_commit_ts)
                VALUES (%s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp())
                RETURNING id, account_id, amount, currency, status, source_commit_ts;
                """,
                (test_id, test_account, test_amount, test_currency, test_status),
            )
            inserted = cur.fetchone()
            assert inserted is not None, "Failed to insert row into source"

    t0 = time.monotonic()
    logger.info("Awaiting replication in warehouse (timeout=%.1fs)...", timeout)

    replicated = False
    elapsed = 0.0
    with psycopg.connect(WAREHOUSE_DB_URL, autocommit=True) as wh_conn:
        while (time.monotonic() - t0) < timeout:
            with wh_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, account_id, amount, currency, status,
                        source_commit_ts, warehouse_arrival_ts
                    FROM ledger
                    WHERE id = %s;
                    """,
                    (test_id,),
                )
                row = cur.fetchone()
                if row is not None:
                    elapsed = time.monotonic() - t0
                    # Validate all business fields
                    assert row[0] == test_id, f"ID mismatch: {row[0]} != {test_id}"
                    assert row[1] == test_account, f"Account mismatch: {row[1]} != {test_account}"
                    amt_match = decimal.Decimal(str(row[2])) == test_amount
                    assert amt_match, f"Amount mismatch: {row[2]} != {test_amount}"
                    curr_match = row[3] == test_currency
                    assert curr_match, f"Currency mismatch: {row[3]} != {test_currency}"
                    assert row[4] == test_status, f"Status mismatch: {row[4]} != {test_status}"
                    replicated = True
                    break
            time.sleep(0.05)

    if not replicated:
        raise TimeoutError(
            f"Smoke test failed: row id={test_id} did not appear in warehouse within {timeout}s"
        )

    logger.info(
        "[SUCCESS] Row id=%d replicated in %.3f s (target <= %.1f s).",
        test_id,
        elapsed,
        timeout,
    )
    return elapsed


def main() -> None:
    try:
        elapsed = run_smoke_test(timeout=10.0)
        print(f"SMOKE_TEST_PASSED: {elapsed:.3f}s")
    except Exception as exc:
        logger.error("Smoke test failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
