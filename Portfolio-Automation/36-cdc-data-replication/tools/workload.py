"""Workload generator for PostgreSQL ledger table using psycopg 3.

Generates a seeded workload (70% inserts, 25% updates, 5% deletes) at a configurable rate,
stamping each row with source_commit_ts.
"""

from __future__ import annotations

import argparse
import decimal
import logging
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("workload")

DEFAULT_SOURCE_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/source_db"
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD"]
STATUSES = ["PENDING", "CONFIRMED", "SETTLED", "RECONCILED", "CANCELLED"]


@dataclass
class WorkloadStats:
    total_ops: int = 0
    inserts: int = 0
    updates: int = 0
    deletes: int = 0
    errors: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    active_ids: set[int] = field(default_factory=set)

    @property
    def duration(self) -> float:
        if self.end_time > self.start_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def actual_rate(self) -> float:
        return self.total_ops / self.duration if self.duration > 0 else 0.0


class WorkloadGenerator:
    """Configurable workload generator with seeded deterministic data generation."""

    def __init__(
        self,
        db_url: str = DEFAULT_SOURCE_URL,
        seed: int = 42,
        target_rate: float = 100.0,
        initial_id: int = 1_000_000,
    ) -> None:
        self.db_url = db_url
        self.rng = random.Random(seed)
        self.target_rate = target_rate
        self.next_id = initial_id
        self.active_id_list: list[int] = []
        self.active_id_set: set[int] = set()
        self._stop_event = threading.Event()
        self.stats = WorkloadStats()

    def generate_insert_row(self) -> tuple[int, str, decimal.Decimal, str, str]:
        row_id = self.next_id
        self.next_id += 1
        account_id = f"acc_{self.rng.randint(1000, 9999)}"
        amount = decimal.Decimal(f"{self.rng.uniform(1.0, 5000.0):.2f}")
        currency = self.rng.choice(CURRENCIES)
        status = self.rng.choice(STATUSES)
        self.active_id_list.append(row_id)
        self.active_id_set.add(row_id)
        return row_id, account_id, amount, currency, status

    def pick_update_row(self) -> tuple[decimal.Decimal, str, int] | None:
        if not self.active_id_list:
            return None
        target_id = self.rng.choice(self.active_id_list)
        new_amount = decimal.Decimal(f"{self.rng.uniform(1.0, 5000.0):.2f}")
        new_status = self.rng.choice(STATUSES)
        return new_amount, new_status, target_id

    def pick_delete_id(self) -> int | None:
        if not self.active_id_list:
            return None
        idx = self.rng.randint(0, len(self.active_id_list) - 1)
        del_id = self.active_id_list.pop(idx)
        self.active_id_set.discard(del_id)
        return del_id

    def stop(self) -> None:
        self._stop_event.set()

    def run(
        self,
        duration_seconds: float | None = None,
        max_ops: int | None = None,
    ) -> WorkloadStats:
        self._stop_event.clear()
        self.stats = WorkloadStats(start_time=time.monotonic())

        # Seed initial pool of 100 rows so updates/deletes have targets
        with psycopg.connect(self.db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                initial_batch = [self.generate_insert_row() for _ in range(100)]
                cur.executemany(
                    """
                    INSERT INTO ledger
                        (id, account_id, amount, currency, status, created_at, source_commit_ts)
                    VALUES (%s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp())
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    initial_batch,
                )
                self.stats.inserts += len(initial_batch)
                self.stats.total_ops += len(initial_batch)

        batch_interval = 0.05  # 50ms intervals
        ops_per_batch = max(1, int(self.target_rate * batch_interval))
        next_tick = time.monotonic()

        with psycopg.connect(self.db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                while not self._stop_event.is_set():
                    now = time.monotonic()
                    if duration_seconds and (now - self.stats.start_time) >= duration_seconds:
                        break
                    if max_ops and self.stats.total_ops >= max_ops:
                        break

                    inserts_data: list[tuple[Any, ...]] = []
                    updates_data: list[tuple[Any, ...]] = []
                    deletes_data: list[int] = []

                    for _ in range(ops_per_batch):
                        roll = self.rng.random()
                        if roll < 0.70 or not self.active_id_list:
                            # 70% inserts
                            inserts_data.append(self.generate_insert_row())
                        elif roll < 0.95:
                            # 25% updates
                            upd = self.pick_update_row()
                            if upd:
                                updates_data.append(upd)
                            else:
                                inserts_data.append(self.generate_insert_row())
                        else:
                            # 5% deletes
                            del_id = self.pick_delete_id()
                            if del_id is not None:
                                deletes_data.append(del_id)
                            else:
                                inserts_data.append(self.generate_insert_row())

                    try:
                        if inserts_data:
                            cur.executemany(
                                """
                                INSERT INTO ledger
                                    (id, account_id, amount, currency, status,
                                     created_at, source_commit_ts)
                                VALUES (%s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp())
                                ON CONFLICT (id) DO NOTHING;
                                """,
                                inserts_data,
                            )
                            self.stats.inserts += len(inserts_data)
                            self.stats.total_ops += len(inserts_data)

                        if updates_data:
                            cur.executemany(
                                """
                                UPDATE ledger
                                SET amount = %s,
                                    status = %s,
                                    source_commit_ts = clock_timestamp()
                                WHERE id = %s;
                                """,
                                updates_data,
                            )
                            self.stats.updates += len(updates_data)
                            self.stats.total_ops += len(updates_data)

                        if deletes_data:
                            cur.execute(
                                "DELETE FROM ledger WHERE id = ANY(%s);",
                                (deletes_data,),
                            )
                            self.stats.deletes += len(deletes_data)
                            self.stats.total_ops += len(deletes_data)

                    except Exception as exc:
                        logger.error("Error executing workload batch: %s", exc)
                        self.stats.errors += 1

                    next_tick += batch_interval
                    sleep_time = next_tick - time.monotonic()
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        next_tick = time.monotonic()

        self.stats.end_time = time.monotonic()
        self.stats.active_ids = self.active_id_set.copy()
        logger.info(
            "Workload complete: %d ops (%d ins, %d upd, %d del, %d err) in %.2fs (%.1f ops/s)",
            self.stats.total_ops,
            self.stats.inserts,
            self.stats.updates,
            self.stats.deletes,
            self.stats.errors,
            self.stats.duration,
            self.stats.actual_rate,
        )
        return self.stats


def preload_ledger_rows(
    db_url: str,
    total_rows: int,
    batch_size: int = 10_000,
    start_id: int = 1,
    seed: int = 42,
) -> float:
    """Preload bulk ledger rows efficiently using PostgreSQL COPY."""
    logger.info(
        "Preloading %d ledger rows into %s (batch size %d)...",
        total_rows,
        db_url,
        batch_size,
    )
    rng = random.Random(seed)
    t0 = time.monotonic()

    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            current_id = start_id
            rows_remaining = total_rows

            while rows_remaining > 0:
                chunk = min(rows_remaining, batch_size)
                # Use COPY for maximum bulk insertion speed
                with cur.copy(
                    """
                    COPY ledger
                        (id, account_id, amount, currency, status, created_at, source_commit_ts)
                    FROM STDIN
                    """
                ) as copy:
                    for _ in range(chunk):
                        acc = f"acc_{rng.randint(1000, 9999)}"
                        amt = f"{rng.uniform(1.0, 5000.0):.2f}"
                        curr = rng.choice(CURRENCIES)
                        st = rng.choice(STATUSES)
                        copy.write_row((current_id, acc, amt, curr, st, "NOW()", "NOW()"))
                        current_id += 1

                rows_remaining -= chunk

    elapsed = time.monotonic() - t0
    rate = total_rows / elapsed if elapsed > 0 else 0
    logger.info("Preloaded %d rows in %.2f s (%.0f rows/s)", total_rows, elapsed, rate)
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ledger workload")
    parser.add_argument("--rate", type=float, default=100.0, help="Target rate in rows/s")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--preload", type=int, default=0, help="Preload N rows using COPY")
    parser.add_argument("--db-url", type=str, default=DEFAULT_SOURCE_URL, help="Database URL")
    args = parser.parse_args()

    if args.preload > 0:
        preload_ledger_rows(args.db_url, args.preload, seed=args.seed)
        sys.exit(0)

    gen = WorkloadGenerator(db_url=args.db_url, seed=args.seed, target_rate=args.rate)
    gen.run(duration_seconds=args.duration)


if __name__ == "__main__":
    main()
