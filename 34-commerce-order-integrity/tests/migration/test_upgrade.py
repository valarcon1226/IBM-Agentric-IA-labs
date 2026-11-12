"""Schema migration and data integrity upgrade test (Saleor N-1 to N).

Requirement: REQ-MIG-001 (Data and Financial Checksum Preservation Across Upgrades)
Validates:
- SQL checksums of orders, lines, totals, stock, and transactions before and after migration.
- Zero checksum differences (assert_target('checksum_differences_upgrade', 0)).
- Migration execution duration measurement.
- API smoke tests passing post-upgrade.
- Rollback procedure verification (snapshot creation and test restore).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import psycopg
import pytest
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target

from tests.client import SaleorGraphQLClient


def calculate_database_checksums(db_url: str) -> dict[str, str]:
    """Calculate cryptographic MD5 checksums for critical business tables."""
    checksums: dict[str, str] = {}
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        # 1. Orders checksum (id, status, total_net_amount, total_gross_amount)
        cur.execute(
            """
            SELECT COALESCE(
                md5(string_agg(id::text || status || total_net_amount::text || total_gross_amount::text, ',' ORDER BY id)),
                'empty'
            )
            FROM order_order
            """
        )
        r = cur.fetchone()
        checksums["pedidos"] = str(r[0]) if r else "empty"

        # 2. Order lines checksum (id, product_variant_id, quantity, unit_price_net_amount, unit_price_gross_amount)
        cur.execute(
            """
            SELECT COALESCE(
                md5(string_agg(id::text || product_variant_id::text || quantity::text || unit_price_net_amount::text || unit_price_gross_amount::text, ',' ORDER BY id)),
                'empty'
            )
            FROM order_orderline
            """
        )
        r = cur.fetchone()
        checksums["lineas"] = str(r[0]) if r else "empty"

        # 3. Totales net y gross
        cur.execute(
            """
            SELECT COALESCE(
                md5(string_agg(total_net_amount::text || total_gross_amount::text, ',' ORDER BY id)),
                'empty'
            )
            FROM order_order
            """
        )
        r = cur.fetchone()
        checksums["totales_net_gross"] = str(r[0]) if r else "empty"

        # 4. Warehouse stock checksum (id, product_variant_id, quantity, quantity_allocated)
        cur.execute(
            """
            SELECT COALESCE(
                md5(string_agg(id::text || product_variant_id::text || quantity::text || quantity_allocated::text, ',' ORDER BY id)),
                'empty'
            )
            FROM warehouse_stock
            """
        )
        r = cur.fetchone()
        checksums["stock"] = str(r[0]) if r else "empty"

        # 5. Payment payment (id, order_id, charge_status, total)
        cur.execute(
            """
            SELECT COALESCE(
                md5(string_agg(id::text || COALESCE(order_id::text, '') || charge_status || total::text, ',' ORDER BY id)),
                'empty'
            )
            FROM payment_payment
            """
        )
        r = cur.fetchone()
        checksums["payment_payment"] = str(r[0]) if r else "empty"

        # 6. Payment transactionitem (id, order_id, charged_value)
        cur.execute(
            """
            SELECT COALESCE(
                md5(string_agg(id::text || COALESCE(order_id::text, '') || charged_value::text, ',' ORDER BY id)),
                'empty'
            )
            FROM payment_transactionitem
            """
        )
        r = cur.fetchone()
        checksums["payment_transactionitem"] = str(r[0]) if r else "empty"

    return checksums


N1_TAG = os.getenv("SALEOR_N1_TAG", "3.19")
N_TAG = os.getenv("SALEOR_N_TAG", "3.20")


def compose(*args: str, tag: str, stdin: str | None = None) -> str:
    """Run docker compose with the Saleor image pinned to `tag`; fail loudly."""
    res = subprocess.run(
        ["docker", "compose", *args],
        env={**os.environ, "SALEOR_TAG": tag},
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, f"docker compose {' '.join(args)} failed:\n{res.stderr}\n{res.stdout}"
    return res.stdout


def count(db_url: str, table: str) -> int:
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")  # table names are literals below
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


@pytest.mark.migration
@pytest.mark.req("REQ-MIG-001")
def test_schema_migration_checksum_preservation(metrics: MetricsRecorder) -> None:
    """Seed Saleor N-1, upgrade the same database to N, compare checksums, then roll back.

    Destructive: recreates the stack, so it runs in its own nightly step.
    """
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")
    api_url = os.getenv("SALEOR_API_URL", "http://127.0.0.1:8000/graphql/")
    client = SaleorGraphQLClient(base_url=api_url)

    # Step 1: fresh N-1 stack with seed data plus 50 orders, each with a payment
    compose("down", "-v", tag=N1_TAG)
    compose("up", "-d", "--wait", tag=N1_TAG)
    seed = subprocess.run(
        [sys.executable, "scripts/seed.py"],
        env={**os.environ, "SALEOR_TAG": N1_TAG},
        check=False, capture_output=True, text=True,
    )
    assert seed.returncode == 0, f"seed failed on {N1_TAG}:\n{seed.stderr}"
    orders_before = count(db_url, "order_order")
    compose(
        "exec", "-T", "api", "python", "manage.py", "shell", "-c",
        "from saleor.core.utils.random_data import create_orders; [print(o) for o in create_orders(50)]",
        tag=N1_TAG,
    )
    assert count(db_url, "order_order") - orders_before == 50
    assert count(db_url, "payment_payment") >= 50

    pre_checksums = calculate_database_checksums(db_url)
    print(f"\n--- Checksums on Saleor {N1_TAG} ---")
    for table_name, csum in pre_checksums.items():
        print(f"  {table_name:24s}: {csum}")

    # Step 2: rollback snapshot taken before migrating
    snapshot = compose("exec", "-T", "postgres", "pg_dump", "-U", "saleor", "--clean", "--if-exists", "saleor", tag=N1_TAG)
    assert len(snapshot) > 10000, "Database snapshot is too small or empty"
    os.makedirs("results", exist_ok=True)
    with open("results/db_snapshot_pre_upgrade.sql", "w", encoding="utf-8") as f_out:
        f_out.write(snapshot)

    # Step 3: stop N-1, migrate the same database with the N image and time it
    compose("stop", "api", "worker", tag=N1_TAG)
    t_start = time.perf_counter()
    mig_out = compose("run", "--rm", "--no-deps", "api", "python", "manage.py", "migrate", "--noinput", tag=N_TAG)
    migration_duration_s = time.perf_counter() - t_start
    applied = mig_out.count("Applying ")
    assert applied > 0, f"No migrations applied going {N1_TAG} -> {N_TAG}; the upgrade was a no-op"
    metrics.record("migration_duration_s", migration_duration_s)
    print(f"Applied {applied} migrations {N1_TAG} -> {N_TAG} in {migration_duration_s:.2f}s")
    compose("up", "-d", "--wait", "api", "worker", tag=N_TAG)

    # Step 4: checksums must match, and the API on N must answer
    post_checksums = calculate_database_checksums(db_url)
    checksum_differences = 0
    print(f"\n--- Checksums on Saleor {N_TAG} ---")
    for table_name, post_csum in post_checksums.items():
        match = post_csum == pre_checksums[table_name]
        print(f"  {table_name:24s}: {post_csum} [{'MATCH' if match else 'DIFF'}]")
        checksum_differences += not match
    assert_target("checksum_differences_upgrade", checksum_differences)
    assert len(client.get_products(first=5).edges) == 5, f"API smoke failed on {N_TAG}"

    # Step 5: rollback = recreate the database, restore the snapshot and boot N-1 on it.
    # Restoring over the N schema is not enough: N adds constraints the N-1 dump cannot drop.
    compose("stop", "api", "worker", tag=N_TAG)
    psql = ("exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", "saleor")
    compose(*psql, "-d", "postgres", "-c", "DROP DATABASE saleor WITH (FORCE)", tag=N1_TAG)
    compose(*psql, "-d", "postgres", "-c", "CREATE DATABASE saleor OWNER saleor", tag=N1_TAG)
    compose(*psql, "-d", "saleor", tag=N1_TAG, stdin=snapshot)
    compose("up", "-d", "--wait", "api", "worker", tag=N1_TAG)
    assert calculate_database_checksums(db_url) == pre_checksums, "Checksums differ after rollback"
    assert len(client.get_products(first=5).edges) == 5, f"API smoke failed after rollback to {N1_TAG}"
    print(f"Rollback verified: {N1_TAG} boots on the restored snapshot with identical checksums")

    # Leave the stack on N for the suites that run after this one
    compose("stop", "api", "worker", tag=N1_TAG)
    compose("up", "-d", "--wait", "api", "worker", tag=N_TAG)
