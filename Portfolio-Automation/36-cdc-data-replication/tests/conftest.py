"""Global pytest configuration and fixtures for CDC replication suite."""

from __future__ import annotations

import re
import subprocess
import time
from typing import Generator

import psycopg
import pytest

from tools.reconcile import (
    DEFAULT_SOURCE_URL,
    DEFAULT_WAREHOUSE_URL,
)


@pytest.fixture(scope="session")
def source_db_url() -> str:
    return DEFAULT_SOURCE_URL


@pytest.fixture(scope="session")
def warehouse_db_url() -> str:
    return DEFAULT_WAREHOUSE_URL


def get_rpk_consumer_lag(group: str = "connect-jdbc-sink") -> int:
    """Query consumer group lag directly from Redpanda broker using rpk.

    Returns -1 if group is rebalancing or not yet stable with members.
    """
    try:
        res = subprocess.run(
            ["docker", "exec", "cdc-redpanda", "rpk", "group", "describe", group],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        stdout = res.stdout

        # Check group stability
        state_match = re.search(r"STATE\s+(\w+)", stdout)
        members_match = re.search(r"MEMBERS\s+(\d+)", stdout)
        if state_match and state_match.group(1) != "Stable":
            return -1
        if members_match and int(members_match.group(1)) == 0:
            return -1

        match = re.search(r"TOTAL-LAG\s+(\d+)", stdout)
        if match:
            return int(match.group(1))

        # Check partition table line for cdc.public.ledger
        for line in stdout.splitlines():
            if "cdc.public.ledger" in line:
                parts = line.split()
                if len(parts) >= 6 and parts[5].isdigit():
                    return int(parts[5])

        return -1
    except Exception:
        return -1


def wait_for_consumer_lag_zero(group: str = "connect-jdbc-sink", timeout: float = 120.0) -> None:
    """Wait until Redpanda reports 0 consumer lag for the group stably."""
    start = time.monotonic()
    consecutive_zero = 0
    last_lag = -1

    while time.monotonic() - start < timeout:
        lag = get_rpk_consumer_lag(group)
        last_lag = lag
        if lag == 0:
            consecutive_zero += 1
            if consecutive_zero >= 2:
                return
        elif lag > 0:
            consecutive_zero = 0
        time.sleep(1.0)

    raise TimeoutError(
        f"Consumer group '{group}' did not reach stable lag 0 "
        f"within {timeout}s (last lag={last_lag})"
    )


def wait_for_cdc_pipeline_idle(timeout: float = 120.0) -> None:
    """Wait until both source Postgres decoding and sink consumption are fully idle."""
    start = time.monotonic()

    # 1. Wait for source replication slot to be active
    while time.monotonic() - start < timeout:
        try:
            with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT active,
                               pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)
                        FROM pg_replication_slots
                        WHERE slot_name = 'debezium_slot';
                        """
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        # Active slot
                        break
        except Exception:
            pass
        time.sleep(1.0)

    # 2. Wait for consumer lag on sink to be 0
    rem_timeout = max(10.0, timeout - (time.monotonic() - start))
    wait_for_consumer_lag_zero("connect-jdbc-sink", timeout=rem_timeout)


@pytest.fixture
def reset_ledger_tables() -> Generator[None, None, None]:
    """Truncate tables before test for clean baseline."""
    with psycopg.connect(DEFAULT_SOURCE_URL, autocommit=True) as s_conn:
        with s_conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ledger;")
    with psycopg.connect(DEFAULT_WAREHOUSE_URL, autocommit=True) as w_conn:
        with w_conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ledger;")
    yield
