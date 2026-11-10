"""Unit tests for keyset pagination reconciler."""

from __future__ import annotations

import decimal
import threading
import time
from collections.abc import Generator

import psycopg
import pytest

from tools.reconcile import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
    reconcile_ledger,
)


@pytest.fixture(autouse=True)
def clean_test_rows() -> Generator[None, None, None]:
    """Clean test range IDs before and after tests."""
    cleanup_sql = "DELETE FROM ledger WHERE id BETWEEN 1 AND 2000;"
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        with s_conn.cursor() as cur:
            cur.execute(cleanup_sql)
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.execute(cleanup_sql)
    yield
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        with s_conn.cursor() as cur:
            cur.execute(cleanup_sql)
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.execute(cleanup_sql)


def test_tampered_warehouse_reconciliation() -> None:
    """Tampering test: 5 rows missing, 5 extra, 5 changed.

    Reconciler must report exactly those 15 differences.
    """
    rows_data = [
        (
            i,
            f"acc_{i}",
            decimal.Decimal("100.00"),
            "USD",
            "CONFIRMED",
        )
        for i in range(1, 101)
    ]

    insert_sql = """
        INSERT INTO ledger (id, account_id, amount, currency, status, created_at, source_commit_ts)
        VALUES (%s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp());
    """

    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        with s_conn.cursor() as cur:
            cur.executemany(insert_sql, rows_data)

    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.executemany(insert_sql, rows_data)

    missing_ids = [10, 20, 30, 40, 50]
    extra_ids = [101, 102, 103, 104, 105]
    changed_ids = [11, 21, 31, 41, 51]

    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.execute("DELETE FROM ledger WHERE id = ANY(%s);", (missing_ids,))

            extra_data = [
                (
                    eid,
                    f"acc_{eid}",
                    decimal.Decimal("999.00"),
                    "USD",
                    "EXTRA",
                )
                for eid in extra_ids
            ]
            cur.executemany(insert_sql, extra_data)

            cur.execute(
                """
                UPDATE ledger
                SET amount = 888.88, status = 'TAMPERED'
                WHERE id = ANY(%s);
                """,
                (changed_ids,),
            )

    result = reconcile_ledger(
        source_url=DEFAULT_SOURCE_URL,
        warehouse_url=DEFAULT_WAREHOUSE_URL,
        chunk_size=20,
        max_id=150,
    )

    assert sorted(result.missing_keys) == sorted(missing_ids)
    assert sorted(result.extra_keys) == sorted(extra_ids)
    assert sorted(result.changed_keys) == sorted(changed_ids)
    assert result.total_differences == 15
    assert not result.is_clean


def test_concurrent_inserts_during_scan_no_false_diffs() -> None:
    """Concurrent writes during scan test.

    REPEATABLE READ snapshot must guarantee 0 false differences.
    """
    base_rows = [
        (
            i,
            f"acc_{i}",
            decimal.Decimal("50.00"),
            "EUR",
            "SETTLED",
        )
        for i in range(501, 701)
    ]
    insert_sql = """
        INSERT INTO ledger (id, account_id, amount, currency, status, created_at, source_commit_ts)
        VALUES (%s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp());
    """

    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        with s_conn.cursor() as cur:
            cur.executemany(insert_sql, base_rows)

    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.executemany(insert_sql, base_rows)

    barrier = threading.Barrier(2)

    def background_writer() -> None:
        barrier.wait()
        time.sleep(0.02)
        extra_concurrent = [
            (
                i,
                f"acc_{i}",
                decimal.Decimal("75.00"),
                "EUR",
                "NEW",
            )
            for i in range(701, 751)
        ]
        with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
            with s_conn.cursor() as cur:
                cur.executemany(insert_sql, extra_concurrent)

    writer_thread = threading.Thread(target=background_writer)
    writer_thread.start()

    barrier.wait()
    result = reconcile_ledger(
        source_url=DEFAULT_SOURCE_URL,
        warehouse_url=DEFAULT_WAREHOUSE_URL,
        chunk_size=50,
        max_id=750,
    )
    writer_thread.join()

    assert result.total_differences == 0
    assert result.is_clean
    assert result.matched_keys == 200
