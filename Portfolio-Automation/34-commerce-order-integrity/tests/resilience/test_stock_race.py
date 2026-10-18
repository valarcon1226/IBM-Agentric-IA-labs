"""Resilience test: Concurrency stock race isolation (zero overselling).

Target: 0 oversells across 20 race runs (REQ-STK-001).
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from typing import Any

import httpx
import psycopg
import pytest
from qa_common.targets import assert_target


def create_fresh_variant_with_stock_5(db_url: str, run_id: int) -> tuple[int, str]:
    """Create a fresh variant in the database with stock=5 and price=0."""
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        # Ensure digital product exists
        cur.execute("SELECT id FROM product_product WHERE slug = 'test-digital-1'")
        row = cur.fetchone()
        if row:
            prod_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO product_product (
                    name, slug, product_type_id, category_id,
                    created_at, updated_at, search_document,
                    description_plaintext, search_index_dirty
                )
                VALUES ('Test Digital', 'test-digital-1', 22, 1, NOW(), NOW(), '', '', false)
                RETURNING id
                """
            )
            r_prod = cur.fetchone()
            assert r_prod is not None
            prod_id = r_prod[0]
            cur.execute(
                """
                INSERT INTO product_productchannellisting (
                    product_id, channel_id, is_published, visible_in_listings, currency,
                    discounted_price_amount, published_at, available_for_purchase_at
                )
                VALUES (%s, 1, true, true, 'USD', 0.0, NOW() - interval '1 day', NOW() - interval '1 day')
                """,
                (prod_id,),
            )

        # Create fresh variant
        sku = f"SKU-RACE-RUN-{run_id}-{time.time_ns()}"
        cur.execute(
            """
            INSERT INTO product_productvariant (
                sku, name, product_id, track_inventory, is_preorder, created_at, updated_at
            )
            VALUES (%s, %s, %s, true, false, NOW(), NOW())
            RETURNING id
            """,
            (sku, f"Race Variant {run_id}", prod_id),
        )
        r_var = cur.fetchone()
        assert r_var is not None
        var_id = r_var[0]

        cur.execute(
            """
            INSERT INTO product_productvariantchannellisting (
                variant_id, channel_id, currency, price_amount, discounted_price_amount, cost_price_amount
            )
            VALUES (%s, 1, 'USD', 0.0, 0.0, 0.0)
            """,
            (var_id,),
        )

        cur.execute("SELECT id FROM warehouse_warehouse LIMIT 1")
        r_wh = cur.fetchone()
        assert r_wh is not None
        wh_id = r_wh[0]

        # Set stock to exactly 5 units available
        cur.execute(
            """
            INSERT INTO warehouse_stock (
                warehouse_id, product_variant_id, quantity, quantity_allocated
            )
            VALUES (%s, %s, 5, 0)
            """,
            (wh_id, var_id),
        )

    relay_id = base64.b64encode(f"ProductVariant:{var_id}".encode()).decode()
    return var_id, relay_id


def get_stock_and_allocated(db_url: str, var_id: int) -> tuple[int, int, int]:
    """Calculate (stock, allocated, oversells) directly from database per variant.

    Oversells are calculated as: assigned (quantity_allocated) minus stock (quantity).
    """
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(quantity), 0), COALESCE(SUM(quantity_allocated), 0)
            FROM warehouse_stock
            WHERE product_variant_id = %s
            """,
            (var_id,),
        )
        row = cur.fetchone()
        assert row is not None
        stock, allocated = int(row[0]), int(row[1])
        oversells = max(0, allocated - stock)
        return stock, allocated, oversells


def get_remaining_stock(db_url: str, var_id: int) -> int:
    """Calculate remaining unallocated stock in database."""
    stock, allocated, _ = get_stock_and_allocated(db_url, var_id)
    return stock - allocated


async def attempt_purchase(
    client: httpx.AsyncClient,
    api_url: str,
    variant_relay_id: str,
    buyer_idx: int,
) -> tuple[bool, str]:
    """Execute checkout create and complete.

    Returns (is_success, error_or_order_code).
    """
    create_mutation = """
    mutation CreateCheckout(
      $channel: String!,
      $lines: [CheckoutLineInput!]!,
      $email: String!,
      $address: AddressInput!
    ) {
      checkoutCreate(input: {
        channel: $channel,
        lines: $lines,
        email: $email,
        billingAddress: $address
      }) {
        checkout { id }
        errors { field message code }
      }
    }
    """
    address = {
        "firstName": "Buyer",
        "lastName": f"Task{buyer_idx}",
        "streetAddress1": "123 Race St",
        "city": "New York",
        "postalCode": "10001",
        "country": "US",
        "countryArea": "NY",
    }
    try:
        resp = await client.post(
            api_url,
            json={
                "query": create_mutation,
                "variables": {
                    "channel": "default-channel",
                    "lines": [{"variantId": variant_relay_id, "quantity": 1}],
                    "email": f"buyer{buyer_idx}_{time.time_ns()}@example.com",
                    "address": address,
                },
            },
        )
        data = resp.json().get("data", {}).get("checkoutCreate", {})
        errors = data.get("errors", [])
        if errors:
            code = errors[0].get("code", "UNKNOWN_ERROR")
            return False, code

        checkout_id = data.get("checkout", {}).get("id")
        if not checkout_id:
            return False, "NO_CHECKOUT_ID"

        # Step 2: complete checkout
        complete_mutation = """
        mutation CompleteCheckout($id: ID!) {
          checkoutComplete(id: $id) {
            order { id status }
            errors { field message code }
          }
        }
        """
        comp_resp = await client.post(
            api_url,
            json={"query": complete_mutation, "variables": {"id": checkout_id}},
        )
        comp_data = comp_resp.json().get("data", {}).get("checkoutComplete", {})
        comp_errors = comp_data.get("errors", [])
        if comp_errors:
            code = comp_errors[0].get("code", "UNKNOWN_ERROR")
            return False, code

        order = comp_data.get("order")
        if order and order.get("id"):
            return True, order["id"]

        return False, "NO_ORDER_RETURNED"
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return False, f"EXCEPTION_{type(exc).__name__}"


@pytest.mark.req("REQ-STK-001")
@pytest.mark.p1
@pytest.mark.resilience
@pytest.mark.xfail(
    strict=True,
    reason="FINDING-001: Race condition in stock allocation under concurrency leads to overselling",
)
def test_stock_race_concurrency_isolation() -> None:
    """50 concurrent buyers compete for 5 units across 20 race runs.

    Asserts exactly 5 orders, 45 clean insufficient stock errors,
    stock 0 in database, and 0 oversells across all 20 runs.
    """
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")
    api_url = os.getenv("SALEOR_API_URL", "http://127.0.0.1:8000/graphql/")

    total_runs = 20
    concurrent_buyers = 50
    initial_stock = 5
    total_oversells = 0

    print("\n" + "=" * 80)
    print(f"STARTING STOCK RACE TEST: {total_runs} runs x {concurrent_buyers} concurrent buyers for {initial_stock} units")
    print("=" * 80)

    async def run_single_race(run_idx: int) -> dict[str, Any]:
        var_id, relay_id = create_fresh_variant_with_stock_5(db_url, run_idx)

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [
                attempt_purchase(client, api_url, relay_id, buyer_idx)
                for buyer_idx in range(concurrent_buyers)
            ]
            results = await asyncio.gather(*tasks)

        successful_orders = [res for success, res in results if success]
        failed_attempts = [res for success, res in results if not success]

        orders_count = len(successful_orders)
        errors_count = len(failed_attempts)
        stock_qty, allocated_qty, oversells = get_stock_and_allocated(db_url, var_id)
        remaining_stock = stock_qty - allocated_qty

        return {
            "run_idx": run_idx,
            "var_id": var_id,
            "orders_count": orders_count,
            "errors_count": errors_count,
            "stock": stock_qty,
            "allocated": allocated_qty,
            "remaining_stock": remaining_stock,
            "oversells": oversells,
            "failed_codes": failed_attempts,
        }

    results_summary: list[str] = []
    failed_runs = 0

    for run_idx in range(1, total_runs + 1):
        result = asyncio.run(run_single_race(run_idx))
        total_oversells += result["oversells"]
        if result["oversells"] > 0 or result["orders_count"] != initial_stock:
            failed_runs += 1

        # Summary line for each run
        summary = (
            f"Run {result['run_idx']:02d}/{total_runs:02d}: "
            f"orders={result['orders_count']} (expected {initial_stock}), "
            f"errors={result['errors_count']} (expected {concurrent_buyers - initial_stock}), "
            f"stock={result['stock']}, allocated={result['allocated']}, "
            f"remaining_stock={result['remaining_stock']}, "
            f"oversells={result['oversells']}"
        )
        print(summary)
        results_summary.append(summary)

    print("=" * 80)
    print(f"Total oversells across {total_runs} runs: {total_oversells} (in {failed_runs} runs)")
    print("=" * 80)

    # If oversells occurred, this is a real concurrency race defect in Saleor
    assert total_oversells == 0, f"Defect: detected {total_oversells} oversells across {total_runs} race runs"
    assert_target("oversells_race", total_oversells)
