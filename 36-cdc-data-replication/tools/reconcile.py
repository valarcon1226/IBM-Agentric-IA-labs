"""Keyset pagination reconciler comparing Postgres source and warehouse tables.

Runs inside a REPEATABLE READ snapshot on each side to ensure snapshot isolation
even during concurrent writes.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Generator

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reconcile")

DEFAULT_SOURCE_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/source_db"
DEFAULT_WAREHOUSE_URL = "postgresql://postgres:postgres_password@127.0.0.1:5436/warehouse_db"


@dataclass
class ReconciliationResult:
    total_source_rows: int = 0
    total_warehouse_rows: int = 0
    matched_keys: int = 0
    missing_keys: list[int] = field(default_factory=list)
    extra_keys: list[int] = field(default_factory=list)
    changed_keys: list[int] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def total_differences(self) -> int:
        return len(self.missing_keys) + len(self.extra_keys) + len(self.changed_keys)

    @property
    def is_clean(self) -> bool:
        return self.total_differences == 0


def _keyset_stream(
    conn: psycopg.Connection,
    table_name: str = "ledger",
    chunk_size: int = 10_000,
    min_id: int | None = None,
    max_id: int | None = None,
    columns: list[str] | None = None,
) -> Generator[tuple[int, str], None, None]:
    """Yields (id, row_hash) tuples in chunks using keyset pagination."""
    last_id = (min_id - 1) if min_id is not None else -1
    cols = (
        columns
        if columns is not None
        else [
            "id::text",
            "account_id::text",
            "round(amount::numeric, 2)::text",
            "currency::text",
            "status::text",
        ]
    )
    cols_sql = ", ".join(cols)
    with conn.cursor() as cur:
        while True:
            if max_id is not None:
                query = f"""
                    SELECT id,
                           md5(concat_ws('|', {cols_sql})) AS row_hash
                    FROM {table_name}
                    WHERE id > %s AND id <= %s
                    ORDER BY id ASC
                    LIMIT %s;
                """
                cur.execute(query, (last_id, max_id, chunk_size))
            else:
                query = f"""
                    SELECT id,
                           md5(concat_ws('|', {cols_sql})) AS row_hash
                    FROM {table_name}
                    WHERE id > %s
                    ORDER BY id ASC
                    LIMIT %s;
                """
                cur.execute(query, (last_id, chunk_size))

            rows = cur.fetchall()
            if not rows:
                break

            for r in rows:
                yield (r[0], r[1])
            last_id = rows[-1][0]


def reconcile_ledger(
    source_url: str = DEFAULT_SOURCE_URL,
    warehouse_url: str = DEFAULT_WAREHOUSE_URL,
    chunk_size: int = 10_000,
    min_id: int | None = None,
    max_id: int | None = None,
    columns: list[str] | None = None,
) -> ReconciliationResult:
    """Compares source and warehouse with keyset pagination under REPEATABLE READ."""
    t0 = time.monotonic()
    result = ReconciliationResult()

    with psycopg.connect(source_url) as src_conn, psycopg.connect(warehouse_url) as wh_conn:
        # Establish repeatable read isolation on both sides
        src_conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        wh_conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ

        with src_conn.transaction(), wh_conn.transaction():
            src_stream = _keyset_stream(
                src_conn, "ledger", chunk_size, min_id=min_id, max_id=max_id, columns=columns
            )
            wh_stream = _keyset_stream(
                wh_conn, "ledger", chunk_size, min_id=min_id, max_id=max_id, columns=columns
            )

            curr_src = next(src_stream, None)
            curr_wh = next(wh_stream, None)

            while curr_src is not None and curr_wh is not None:
                src_id, src_hash = curr_src
                wh_id, wh_hash = curr_wh

                if src_id == wh_id:
                    result.total_source_rows += 1
                    result.total_warehouse_rows += 1
                    if src_hash == wh_hash:
                        result.matched_keys += 1
                    else:
                        result.changed_keys.append(src_id)
                    curr_src = next(src_stream, None)
                    curr_wh = next(wh_stream, None)
                elif src_id < wh_id:
                    result.total_source_rows += 1
                    result.missing_keys.append(src_id)
                    curr_src = next(src_stream, None)
                else:
                    result.total_warehouse_rows += 1
                    result.extra_keys.append(wh_id)
                    curr_wh = next(wh_stream, None)

            # Drain remaining source rows
            while curr_src is not None:
                result.total_source_rows += 1
                result.missing_keys.append(curr_src[0])
                curr_src = next(src_stream, None)

            # Drain remaining warehouse rows
            while curr_wh is not None:
                result.total_warehouse_rows += 1
                result.extra_keys.append(curr_wh[0])
                curr_wh = next(wh_stream, None)

    result.elapsed_seconds = time.monotonic() - t0
    logger.info(
        "Reconciliation finished in %.2f s: "
        "Source=%d, Warehouse=%d, Matched=%d, Missing=%d, Extra=%d, Changed=%d (Diffs=%d)",
        result.elapsed_seconds,
        result.total_source_rows,
        result.total_warehouse_rows,
        result.matched_keys,
        len(result.missing_keys),
        len(result.extra_keys),
        len(result.changed_keys),
        result.total_differences,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile source and warehouse ledger tables")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Source DB URL")
    parser.add_argument("--warehouse-url", default=DEFAULT_WAREHOUSE_URL, help="Warehouse DB URL")
    parser.add_argument("--chunk-size", type=int, default=10_000, help="Chunk size (default 10000)")
    parser.add_argument("--max-id", type=int, default=None, help="Optional max id limit")
    args = parser.parse_args()

    res = reconcile_ledger(
        source_url=args.source_url,
        warehouse_url=args.warehouse_url,
        chunk_size=args.chunk_size,
        max_id=args.max_id,
    )
    if not res.is_clean:
        print(f"RECONCILIATION_FAILED: {res.total_differences} differences found")
        sys.exit(1)
    else:
        print(f"RECONCILIATION_PASSED: 0 differences in {res.elapsed_seconds:.2f}s")


if __name__ == "__main__":
    main()
