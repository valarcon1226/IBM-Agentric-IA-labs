"""Pagination integrity and boundary validation tests.

Citations:
- Maximum pagination limit is enforced in Saleor 3.20 source at:
  saleor/graphql/core/connection.py:387-394
  "Requesting {first} records on the `{info.field_name}` connection exceeds the `first` limit of {max_limit} records."
  Default GRAPHQL_PAGINATION_LIMIT = 100.
"""

from __future__ import annotations

import base64
import os
import threading
import time

import psycopg
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.client import GraphQLError, SaleorGraphQLClient


def decode_relay_id(relay_id: str) -> int:
    """Decode GraphQL base64 Relay ID to database integer primary key."""
    decoded = base64.b64decode(relay_id).decode("utf-8")
    return int(decoded.split(":")[-1])


def get_db_product_ids(db_url: str) -> set[int]:
    """Fetch visible product IDs for default-channel directly from PostgreSQL."""
    query = """
    SELECT p.id
    FROM product_product p
    JOIN product_productchannellisting cl ON cl.product_id = p.id
    JOIN channel_channel ch ON ch.id = cl.channel_id
    WHERE ch.slug = 'default-channel' AND cl.visible_in_listings = true
    """
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(query)
        return {row[0] for row in cur.fetchall()}


@pytest.mark.req("REQ-CAT-001")
@pytest.mark.p1
@settings(max_examples=5, deadline=None)
@given(page_size=st.integers(min_value=1, max_value=100))
def test_hypothesis_product_pagination_walk(page_size: int) -> None:
    """Hypothesis test walking products with page sizes 1 to 100.

    The set of IDs collected must equal the set from direct SQL query,
    with zero duplicates.
    """
    client = SaleorGraphQLClient()
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")

    expected_db_ids = get_db_product_ids(db_url)
    assert len(expected_db_ids) > 0

    collected_db_ids: list[int] = []
    has_next = True
    after_cursor: str | None = None

    while has_next:
        conn = client.get_products(first=page_size, after=after_cursor)
        for edge in conn.edges:
            collected_db_ids.append(decode_relay_id(edge.node.id))

        has_next = conn.page_info.has_next_page
        after_cursor = conn.page_info.end_cursor

    # Assert no duplicates
    assert len(collected_db_ids) == len(set(collected_db_ids)), "Duplicate product ID encountered during walk"

    # Assert exact match with database set
    assert set(collected_db_ids) == expected_db_ids, "Collected IDs do not match database visible products"


@pytest.mark.req("REQ-CAT-001")
@pytest.mark.p1
def test_pagination_concurrent_inserts() -> None:
    """Test that concurrent product insertions during walk never repeat or skip pre-existing IDs."""
    client = SaleorGraphQLClient()
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")

    initial_ids = get_db_product_ids(db_url)
    assert len(initial_ids) > 0

    inserted_ids: list[int] = []
    stop_event = threading.Event()

    def insert_products() -> None:
        with psycopg.connect(db_url, autocommit=True) as db_conn, db_conn.cursor() as cur:
            # Retrieve channel_id, category_id, product_type_id
            cur.execute("SELECT id FROM channel_channel WHERE slug = 'default-channel'")
            r_chan = cur.fetchone()
            assert r_chan is not None
            channel_id = r_chan[0]

            cur.execute("SELECT id FROM product_producttype LIMIT 1")
            r_pt = cur.fetchone()
            assert r_pt is not None
            product_type_id = r_pt[0]

            cur.execute("SELECT id FROM product_category LIMIT 1")
            r_cat = cur.fetchone()
            assert r_cat is not None
            category_id = r_cat[0]

            for i in range(200):
                if stop_event.is_set():
                    break
                slug = f"conc-test-prod-{time.time_ns()}-{i}"
                cur.execute(
                    """
                    INSERT INTO product_product (
                        name, slug, product_type_id, category_id,
                        created_at, updated_at, search_document,
                        description_plaintext, search_index_dirty
                    )
                    VALUES (%s, %s, %s, %s, NOW(), NOW(), '', '', false)
                    RETURNING id
                    """,
                    (f"Concurrent Product {i}", slug, product_type_id, category_id),
                )
                r_prod = cur.fetchone()
                assert r_prod is not None
                prod_id = r_prod[0]
                cur.execute(
                    """
                    INSERT INTO product_productchannellisting (
                        product_id, channel_id, is_published, visible_in_listings, currency, discounted_price_amount
                    )
                    VALUES (%s, %s, true, true, 'USD', 10.0)
                    """,
                    (prod_id, channel_id),
                )
                inserted_ids.append(prod_id)
                time.sleep(0.01)

    insert_thread = threading.Thread(target=insert_products, daemon=True)
    insert_thread.start()

    collected_ids: list[int] = []
    has_next = True
    after_cursor: str | None = None

    try:
        while has_next:
            conn = client.get_products(first=5, after=after_cursor)
            for edge in conn.edges:
                collected_ids.append(decode_relay_id(edge.node.id))
            has_next = conn.page_info.has_next_page
            after_cursor = conn.page_info.end_cursor
            time.sleep(0.02)
    finally:
        stop_event.set()
        insert_thread.join(timeout=10.0)

        # Cleanup inserted records
        if inserted_ids:
            with psycopg.connect(db_url, autocommit=True) as db_conn, db_conn.cursor() as cur:
                cur.execute("DELETE FROM product_productchannellisting WHERE product_id = ANY(%s)", (inserted_ids,))
                cur.execute("DELETE FROM product_product WHERE id = ANY(%s)", (inserted_ids,))

    # 1. No ID may repeat
    assert len(collected_ids) == len(set(collected_ids)), "Duplicate product ID encountered during concurrent walk"

    # 2. No product that existed before the walk may be skipped
    assert initial_ids.issubset(set(collected_ids)), "A pre-existing product was skipped during concurrent walk"


@pytest.mark.req("REQ-CAT-001")
@pytest.mark.p1
def test_first_above_maximum_limit_returns_documented_error() -> None:
    """Documented limit test.

    Saleor 3.20 enforces a maximum limit of 100 in saleor/graphql/core/connection.py:387.
    Requesting first=101 must raise GraphQLError with documented message.
    """
    client = SaleorGraphQLClient()

    with pytest.raises(GraphQLError) as exc_info:
        client.get_products(first=101)

    error_msg = str(exc_info.value)
    # Validate documented error string
    assert "exceeds the `first` limit of 100 records" in error_msg


def ensure_at_least_2000_orders(db_url: str) -> int:
    """Ensure at least 2,000 orders exist in database for pagination walk."""
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM order_order")
        r = cur.fetchone()
        current_count = r[0] if r else 0
        if current_count < 2000:
            needed = 2005 - current_count
            cur.execute(
                """
                INSERT INTO order_order (
                    id, number, channel_id, status, user_email, currency, language_code,
                    tracking_client_id, customer_note, checkout_token, origin, authorize_status, charge_status,
                    total_net_amount, total_gross_amount, undiscounted_total_net_amount, undiscounted_total_gross_amount,
                    subtotal_net_amount, subtotal_gross_amount, total_charged_amount, total_authorized_amount,
                    base_shipping_price_amount, shipping_price_net_amount, shipping_price_gross_amount,
                    weight, display_gross_prices, should_refresh_prices, use_old_id, tax_exemption,
                    search_document, created_at, updated_at
                )
                SELECT
                    gen_random_uuid(),
                    nextval('order_order_number_seq'),  -- keeps Saleor's own numbering valid
                    1,
                    'unfulfilled',
                    'walk_order_' || s || '@example.com',
                    'USD',
                    'en',
                    '',
                    '',
                    '',
                    'checkout',
                    'none',
                    'none',
                    10.000, 10.000, 10.000, 10.000,
                    10.000, 10.000, 0.000, 0.000,
                    0.000, 0.000, 0.000,
                    0.0,
                    true,
                    false,
                    false,
                    false,
                    '',
                    NOW(),
                    NOW()
                FROM generate_series(1, %s) s;
                """,
                (needed,),
            )
            cur.execute("SELECT count(*) FROM order_order")
            r_after = cur.fetchone()
            return r_after[0] if r_after else current_count + needed
        return current_count


@pytest.mark.req("REQ-CAT-001")
@pytest.mark.p1
def test_order_pagination_walk_2000_orders() -> None:
    """Walk at least 2,000 orders using GraphQL orders connection in batches of 100.

    Validates:
    - Traversal reaches at least 2,000 orders.
    - Zero duplicates across all pages (no repeated order IDs).
    - PageInfo.has_next_page and PageInfo.end_cursor properly advance cursor.
    """
    client = SaleorGraphQLClient()
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")

    total_in_db = ensure_at_least_2000_orders(db_url)
    assert total_in_db >= 2000

    token = client.execute(
        """
        mutation TokenCreate($email: String!, $password: String!) {
          tokenCreate(email: $email, password: $password) {
            token
          }
        }
        """,
        {"email": "admin@example.com", "password": "admin"},
    )["tokenCreate"]["token"]

    query = """
    query OrdersWalk($first: Int!, $after: String) {
      orders(first: $first, after: $after) {
        totalCount
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            id
            number
          }
        }
      }
    }
    """

    collected_order_ids: list[str] = []
    has_next = True
    after_cursor: str | None = None
    target_count = 2000

    while has_next and len(collected_order_ids) < target_count:
        data = client.execute(
            query,
            variables={"first": 100, "after": after_cursor},
            token=token,
        )
        orders_conn = data["orders"]
        edges = orders_conn.get("edges", [])
        assert len(edges) > 0, "Expected non-empty page of orders"
        for edge in edges:
            collected_order_ids.append(edge["node"]["id"])

        page_info = orders_conn["pageInfo"]
        has_next = page_info["hasNextPage"]
        after_cursor = page_info["endCursor"]

    print(f"\nTraversed {len(collected_order_ids)} orders via GraphQL pagination (target: {target_count})")
    assert len(collected_order_ids) >= target_count, f"Expected at least {target_count} orders, got {len(collected_order_ids)}"
    assert len(collected_order_ids) == len(set(collected_order_ids)), "Duplicate order ID encountered during pagination walk"

