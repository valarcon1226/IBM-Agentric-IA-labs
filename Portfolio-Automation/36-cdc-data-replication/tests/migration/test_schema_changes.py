"""Schema migration tests under continuous load (REQ-CDC-006).

Validates four real-world expand/contract migration scenarios under a 200 rows/s workload:
1. Add nullable column, backfill it, then SET NOT NULL.
2. Rename column using expand/contract (add, copy, switch writer, drop).
3. Widen type (int to bigint).
4. Add column with default.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx
import psycopg
import pytest

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    wait_for_cdc_pipeline_idle,
)
from tools.reconcile import reconcile_ledger
from tools.workload import WorkloadGenerator

logger = logging.getLogger("test_schema_changes")
CONNECT_URL = "http://127.0.0.1:8083"


def _restart_sink_task() -> None:
    """Restart JDBC sink task so Hibernate clears its cached table schema."""
    try:
        httpx.post(f"{CONNECT_URL}/connectors/jdbc-sink/tasks/0/restart", timeout=10.0)
        time.sleep(3.0)
    except Exception as exc:
        logger.warning("Failed to restart sink task: %s", exc)


def _column_exists_in_warehouse(column_name: str) -> bool:
    """Check if column exists in the warehouse ledger table."""
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'ledger' AND column_name = %s;
                """,
                (column_name,),
            )
            return bool(cur.fetchone())


def _column_type_in_warehouse(column_name: str) -> str | None:
    """Get the data type of a column in the warehouse ledger table."""
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'ledger' AND column_name = %s;
                """,
                (column_name,),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None


@pytest.mark.migration
@pytest.mark.req("REQ-CDC-006")
def test_migration_1_add_nullable_backfill_set_not_null() -> None:
    """Scenario 1: Add a nullable column, backfill it, then SET NOT NULL under 200 rows/s load.

    Outcome:
    Debezium schema evolution adds the column to the warehouse automatically.
    The backfill and NOT NULL constraint succeed on the source.
    Warehouse inherits the column and reconciliation shows 0 differences.
    """
    logger.info("Starting Scenario 1: Add nullable, backfill, SET NOT NULL under load...")
    col = "tier_code"
    base_id = int(time.time() * 1000)

    # Clean up column if lingering from prior test run
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        w_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
    _restart_sink_task()

    wg = WorkloadGenerator(DEFAULT_SOURCE_URL, target_rate=200.0, seed=101, initial_id=base_id)
    workload_thread = threading.Thread(target=wg.run, args=(8.0,), daemon=True)
    workload_thread.start()

    try:
        time.sleep(1.5)
        # Step 1: Add nullable column on source
        logger.info("Step 1: Adding nullable column '%s' on source...", col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger ADD COLUMN IF NOT EXISTS {col} text;")

        time.sleep(1.5)
        # Step 2: Set default so concurrent inserts never receive NULL
        logger.info("Step 2: Setting default on source column '%s'...", col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger ALTER COLUMN {col} SET DEFAULT 'STANDARD';")

        time.sleep(1.0)
        # Step 3: Backfill any rows inserted before the default was set
        logger.info("Step 3: Backfilling column '%s' on source...", col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(
                f"UPDATE ledger SET {col} = 'STANDARD' WHERE {col} IS NULL;"
            )

        time.sleep(1.0)
        # Step 4: Set NOT NULL on source (safe: all past rows backfilled, future rows get default)
        logger.info("Step 4: Setting NOT NULL on source column '%s'...", col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger ALTER COLUMN {col} SET NOT NULL;")

        workload_thread.join(timeout=20.0)
        logger.info("Workload completed. Awaiting pipeline idle...")
        wait_for_cdc_pipeline_idle(timeout=60.0)

        # Assert column was created in warehouse by Debezium basic schema evolution
        assert _column_exists_in_warehouse(col), f"Column '{col}' was not added to warehouse"

        # Reconcile test rows including the new column
        cols_to_check = [
            "id::text",
            "account_id::text",
            "round(amount::numeric, 2)::text",
            "currency::text",
            "status::text",
            f"COALESCE({col}, 'STANDARD')::text",
        ]
        rec = reconcile_ledger(min_id=base_id, columns=cols_to_check)
        logger.info(
            "Scenario 1 Reconcile: Source=%d, Warehouse=%d, Diffs=%d",
            rec.total_source_rows,
            rec.total_warehouse_rows,
            rec.total_differences,
        )
        assert rec.is_clean, f"Reconciliation found differences: {rec.total_differences}"

    finally:
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
        wait_for_cdc_pipeline_idle(timeout=60.0)


@pytest.mark.migration
@pytest.mark.req("REQ-CDC-006")
def test_migration_2_rename_column_expand_contract() -> None:
    """Scenario 2: Rename a column using expand/contract (add, copy, switch, drop) under load.

    Outcome:
    Debezium schema evolution adds the new column to the warehouse.
    When the source drops the old column, basic schema evolution preserves the old column
    in the warehouse without dropping it (non-destructive).
    Reconciliation verifies that all active columns match with 0 differences.
    """
    logger.info("Starting Scenario 2: Rename column via Expand/Contract under load...")
    old_col = "tag_old"
    new_col = "tag_new"
    base_id = int(time.time() * 1000)

    # Pre-populate old column
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        s_conn.execute(f"ALTER TABLE ledger ADD COLUMN IF NOT EXISTS {old_col} text DEFAULT 'TAG';")
        s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {new_col};")
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        w_conn.execute(f"ALTER TABLE ledger ADD COLUMN IF NOT EXISTS {old_col} text DEFAULT 'TAG';")
        w_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {new_col};")
    _restart_sink_task()

    wg = WorkloadGenerator(DEFAULT_SOURCE_URL, target_rate=200.0, seed=102, initial_id=base_id)
    workload_thread = threading.Thread(target=wg.run, args=(8.0,), daemon=True)
    workload_thread.start()

    try:
        time.sleep(1.5)
        # Step 1: Expand - add new column
        logger.info("Step 1 (Expand): Adding '%s' to source...", new_col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger ADD COLUMN IF NOT EXISTS {new_col} text;")

        time.sleep(1.5)
        # Step 2: Copy - backfill data from old to new
        logger.info(
            "Step 2 (Copy): Copying data from '%s' to '%s'...",
            old_col,
            new_col,
        )
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(
                f"UPDATE ledger SET {new_col} = {old_col} WHERE {new_col} IS NULL;"
            )

        time.sleep(1.5)
        # Step 3: Contract - drop old column on source
        logger.info("Step 3 (Contract): Dropping '%s' on source...", old_col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {old_col};")

        workload_thread.join(timeout=20.0)
        wait_for_cdc_pipeline_idle(timeout=60.0)

        # Assert new column exists in warehouse
        assert _column_exists_in_warehouse(new_col), f"New column '{new_col}' missing in warehouse"

        # Assert old column still exists in warehouse (schema.evolution: basic is additive only)
        assert _column_exists_in_warehouse(old_col), (
            f"Expected old column '{old_col}' to be preserved in warehouse"
        )

        # Reconcile on active schema
        cols = [
            "id::text",
            "account_id::text",
            "round(amount::numeric, 2)::text",
            "currency::text",
            "status::text",
            f"COALESCE({new_col}, 'TAG')::text",
        ]
        rec = reconcile_ledger(min_id=base_id, columns=cols)
        logger.info(
            "Scenario 2 Reconcile: Source=%d, Warehouse=%d, Diffs=%d",
            rec.total_source_rows,
            rec.total_warehouse_rows,
            rec.total_differences,
        )
        assert rec.is_clean, f"Reconciliation found differences: {rec.total_differences}"

    finally:
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {old_col};")
            s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {new_col};")
        wait_for_cdc_pipeline_idle(timeout=60.0)


@pytest.mark.migration
@pytest.mark.req("REQ-CDC-006")
def test_migration_3_widen_int_to_bigint() -> None:
    """Scenario 3: Widen int to bigint under load.

    Analysis:
    Debezium schema.evolution=basic does not ALTER existing column data types in the target.
    Therefore, the safe operational pattern is:
    1. Pre-widen the warehouse column to bigint (forward-compatible).
    2. Then widen the source column to bigint.
    3. Large 64-bit values (> 2^31-1) replicate cleanly without overflow or task failure.
    """
    logger.info("Starting Scenario 3: Widen type int to bigint under load...")
    col = "sequence_num"
    base_id = int(time.time() * 1000)

    # Setup column as int on source and warehouse initially
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
        s_conn.execute(f"ALTER TABLE ledger ADD COLUMN {col} int DEFAULT 1;")
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        w_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
        w_conn.execute(f"ALTER TABLE ledger ADD COLUMN {col} int DEFAULT 1;")
    _restart_sink_task()
    wait_for_cdc_pipeline_idle(timeout=20.0)

    wg = WorkloadGenerator(DEFAULT_SOURCE_URL, target_rate=200.0, seed=103, initial_id=base_id)
    workload_thread = threading.Thread(target=wg.run, args=(8.0,), daemon=True)
    workload_thread.start()

    try:
        time.sleep(1.5)
        # Step 1: Widen warehouse FIRST (safe pattern)
        logger.info("Step 1: Widening warehouse column '%s' to bigint...", col)
        with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
            w_conn.execute(f"ALTER TABLE ledger ALTER COLUMN {col} TYPE bigint;")

        time.sleep(1.5)
        # Step 2: Widen source to bigint
        logger.info("Step 2: Widening source column '%s' to bigint...", col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger ALTER COLUMN {col} TYPE bigint;")

        # Step 3: Insert 64-bit large values exceeding 32-bit int max (2,147,483,647)
        large_val = 5_000_000_000
        logger.info("Step 3: Inserting large 64-bit value (%d) into '%s'...", large_val, col)
        big_id = base_id + 8888
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(
                f"""
                INSERT INTO ledger (
                    id, account_id, amount, currency, status, {col}, created_at, source_commit_ts
                ) VALUES (
                    {big_id}, 'acc_big_{big_id}', 100.00, 'USD', 'NEW', {large_val},
                    clock_timestamp(), clock_timestamp()
                );
                """
            )

        workload_thread.join(timeout=20.0)
        wait_for_cdc_pipeline_idle(timeout=60.0)

        # Assert warehouse holds the large value correctly
        with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
            with w_conn.cursor() as cur:
                cur.execute(f"SELECT {col} FROM ledger WHERE id = %s;", (big_id,))
                row = cur.fetchone()
                assert row is not None
                assert row[0] == large_val, f"Expected {large_val}, got {row[0]}"

        # Assert warehouse type is bigint
        wh_type = _column_type_in_warehouse(col)
        assert wh_type == "bigint", f"Expected bigint in warehouse, got {wh_type}"

        # Reconcile on active columns
        cols = [
            "id::text",
            "account_id::text",
            "round(amount::numeric, 2)::text",
            "currency::text",
            "status::text",
            f"COALESCE({col}, 1)::text",
        ]
        rec = reconcile_ledger(min_id=base_id, columns=cols)
        logger.info(
            "Scenario 3 Reconcile: Source=%d, Warehouse=%d, Diffs=%d",
            rec.total_source_rows,
            rec.total_warehouse_rows,
            rec.total_differences,
        )
        assert rec.is_clean, f"Reconciliation found differences: {rec.total_differences}"

    finally:
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
        wait_for_cdc_pipeline_idle(timeout=60.0)


@pytest.mark.migration
@pytest.mark.req("REQ-CDC-006")
def test_migration_4_add_column_with_default() -> None:
    """Scenario 4: Add column with a default under load.

    Outcome:
    PostgreSQL 11+ applies ADD COLUMN ... DEFAULT as a metadata-only instant DDL.
    Debezium captures the DDL and includes the default in the event schema.
    JDBC sink creates the column in the warehouse.
    Existing and newly inserted rows reconcile with 0 differences.
    """
    logger.info("Starting Scenario 4: Add column with DEFAULT under load...")
    col = "priority_level"
    base_id = int(time.time() * 1000)

    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        w_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
    _restart_sink_task()

    wg = WorkloadGenerator(DEFAULT_SOURCE_URL, target_rate=200.0, seed=104, initial_id=base_id)
    workload_thread = threading.Thread(target=wg.run, args=(8.0,), daemon=True)
    workload_thread.start()

    try:
        time.sleep(1.5)
        logger.info("Adding column '%s' with DEFAULT 5 on source...", col)
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger ADD COLUMN IF NOT EXISTS {col} int DEFAULT 5;")

        workload_thread.join(timeout=20.0)
        wait_for_cdc_pipeline_idle(timeout=60.0)

        # Assert column was created in warehouse
        assert _column_exists_in_warehouse(col), f"Column '{col}' was not added to warehouse"

        # Reconcile on active columns
        cols = [
            "id::text",
            "account_id::text",
            "round(amount::numeric, 2)::text",
            "currency::text",
            "status::text",
            f"COALESCE({col}, 5)::text",
        ]
        rec = reconcile_ledger(min_id=base_id, columns=cols)
        logger.info(
            "Scenario 4 Reconcile: Source=%d, Warehouse=%d, Diffs=%d",
            rec.total_source_rows,
            rec.total_warehouse_rows,
            rec.total_differences,
        )
        assert rec.is_clean, f"Reconciliation found differences: {rec.total_differences}"

    finally:
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            s_conn.execute(f"ALTER TABLE ledger DROP COLUMN IF EXISTS {col};")
        wait_for_cdc_pipeline_idle(timeout=60.0)
