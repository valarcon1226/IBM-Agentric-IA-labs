"""Resilience test: Client retry idempotency on network connection drop.

Citations on Idempotency in Saleor 3.20:
1. checkoutComplete:
   Source file: saleor/checkout/complete_checkout.py:1664-1667
   Implementation:
       with transaction_with_commit_on_errors():
           checkout = Checkout.objects.select_for_update().filter(pk=checkout_pk).first()
           if not checkout:
               order = Order.objects.get_by_checkout_token(checkout_pk)
               return order, False, {}
   The checkout token itself acts as the idempotency key: upon completion, the checkout
   record is deleted, and any subsequent retry looking up the checkout token resolves
   directly to the already-created order via `get_by_checkout_token`.

2. transactionInitialize & transactionProcess:
   Source file: saleor/graphql/payment/mutations/transaction/transaction_initialize.py:61-68, 132-144, 202-215
   Implementation:
       idempotency_key = graphene.String(description="The idempotency key assigned to the action...")
       If a duplicate call with the same idempotency_key is made, the existing transaction
       is returned; if conflicting parameters are sent, TransactionInitializeErrorCode.UNIQUE is raised.
"""

from __future__ import annotations

import base64
import os
import time

import httpx
import psycopg
import pytest
from qa_common.targets import assert_target
from qa_common.toxiproxy import ToxiproxyClient

from tests.client import SaleorGraphQLClient


def get_test_variant_relay_id(db_url: str) -> str:
    """Ensure a reusable digital variant with ample stock exists."""
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM product_product WHERE slug = 'test-digital-retry'")
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
                VALUES ('Retry Digital Product', 'test-digital-retry', 22, 1, NOW(), NOW(), '', '', false)
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

        cur.execute("SELECT id FROM product_productvariant WHERE sku = 'SKU-RETRY-COMMON'")
        var_row = cur.fetchone()
        if var_row:
            var_id = var_row[0]
            # Top up stock with ample quantity and disable inventory tracking
            cur.execute(
                "UPDATE product_productvariant SET track_inventory = false WHERE id = %s",
                (var_id,),
            )
            cur.execute(
                "UPDATE warehouse_stock SET quantity = 100000, quantity_allocated = 0 WHERE product_variant_id = %s",
                (var_id,),
            )
        else:
            cur.execute(
                """
                INSERT INTO product_productvariant (
                    sku, name, product_id, track_inventory, is_preorder, created_at, updated_at
                )
                VALUES ('SKU-RETRY-COMMON', 'Retry Variant', %s, true, false, NOW(), NOW())
                RETURNING id
                """,
                (prod_id,),
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

            cur.execute(
                """
                INSERT INTO warehouse_stock (
                    warehouse_id, product_variant_id, quantity, quantity_allocated
                )
                VALUES (%s, %s, 500, 0)
                """,
                (wh_id, var_id),
            )

    return base64.b64encode(f"ProductVariant:{var_id}".encode()).decode()


def count_orders_for_checkout(db_url: str, checkout_token: str) -> int:
    """Count how many orders exist in database for a given checkout token."""
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM order_order WHERE checkout_token = %s",
            (checkout_token,),
        )
        r_cnt = cur.fetchone()
        assert r_cnt is not None
        return int(r_cnt[0])


@pytest.mark.req("REQ-CHK-001")
@pytest.mark.p1
@pytest.mark.resilience
def test_checkout_complete_retry_idempotency_50_runs() -> None:
    """Cuts network connection downstream after checkout reaches server, then retries.

    Asserts exactly 1 order in the database for each checkout across 50 runs.
    """
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")
    api_url = os.getenv("SALEOR_API_URL", "http://127.0.0.1:8000/graphql/")
    toxi_url = os.getenv("TOXIPROXY_URL", "http://127.0.0.1:8474")

    toxi_client = ToxiproxyClient(base_url=toxi_url)
    saleor_client = SaleorGraphQLClient(base_url=api_url)

    variant_relay_id = get_test_variant_relay_id(db_url)
    total_runs = 50
    duplicate_orders = 0

    print("\n" + "=" * 80)
    print(f"STARTING CLIENT RETRY IDEMPOTENCY TEST: {total_runs} iterations through Toxiproxy")
    print("=" * 80)

    for run_idx in range(1, total_runs + 1):
        # 1. Create a fresh checkout
        email = f"retry_buyer_{run_idx}_{time.time_ns()}@example.com"
        checkout = saleor_client.create_checkout(variant_id=variant_relay_id, quantity=1, email=email)
        checkout_id = checkout.id

        # Extract UUID token from relay ID
        decoded = base64.b64decode(checkout_id).decode()
        checkout_token = decoded.split(":")[-1]

        # 2. Add downstream reset_peer / timeout toxic
        toxic_name = f"cut_downstream_{run_idx}"
        toxi_client.add_toxic(
            proxy_name="saleor_api",
            toxic_name=toxic_name,
            toxic_type="reset_peer",
            stream="downstream",
            toxicity=1.0,
            attributes={"timeout": 150},
        )

        # 3. Client sends checkoutComplete through Toxiproxy
        try:
            with httpx.Client(timeout=1.0) as quick_client:
                complete_mutation = """
                mutation CompleteCheckout($id: ID!) {
                  checkoutComplete(id: $id) {
                    order { id status }
                    errors { field message code }
                  }
                }
                """
                quick_client.post(
                    api_url,
                    json={"query": complete_mutation, "variables": {"id": checkout_id}},
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            # Expected: connection cut by Toxiproxy on downstream
            pass
        finally:
            toxi_client.remove_toxic(proxy_name="saleor_api", toxic_name=toxic_name)

        # Wait briefly for transaction commit
        time.sleep(0.05)

        # 4. Client retries checkoutComplete
        retry_res = saleor_client.complete_checkout(checkout_id=checkout_id)
        assert retry_res.order is not None, f"Retry on run {run_idx} did not return order"

        # 5. Verify database order count for this checkout
        order_count = count_orders_for_checkout(db_url, checkout_token)
        if order_count > 1:
            duplicate_orders += (order_count - 1)

        assert order_count == 1, (
            f"Run {run_idx}: Duplicate orders detected! Found {order_count} orders "
            f"for checkout token {checkout_token}"
        )

        if run_idx % 10 == 0 or run_idx == total_runs:
            print(f"Progress: {run_idx}/{total_runs} runs completed. Orders per checkout: {order_count}, Duplicates: 0")

    # Assert target from targets.toml
    assert_target("duplicate_orders_retry", duplicate_orders)
    print("=" * 80)
    print(f"IDEMPOTENCY TEST PASSED: Exactly 1 order per checkout across all {total_runs} runs.")
    print("=" * 80)
