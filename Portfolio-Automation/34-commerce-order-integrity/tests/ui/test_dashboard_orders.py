"""Staff Dashboard Playwright UI tests for Order Lifecycle Management.

Requirement: REQ-UI-001 (Staff Dashboard Order Lifecycle and Refund Management)
Verifies 5 critical staff user journeys:
1. Staff authentication and dashboard access.
2. Locating and viewing order details for a freshly created order.
3. Fulfilling an unfulfilled order through UI and verifying exact FULFILLED status via API.
4. Issuing a partial refund through UI and verifying exact refunded amount via API.
5. Verifying refund reflection in order history timeline through UI and exact event via API.

Adheres strictly to QA policy:
- UI tests user interactions only; setups and assertions are backed by API/database.
- No `if is_visible()` or `if not is_disabled()`; missing steps must fail the test.
- Role-based and accessible locators.
- Staff credentials loaded from environment variables.
- Tracing captured on failure.
"""

from __future__ import annotations

import base64
import os
import urllib.parse

import psycopg
import pytest
from playwright.sync_api import Page, expect

from tests.client import SaleorGraphQLClient

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:9000")
API_URL = os.getenv("SALEOR_API_URL", "http://127.0.0.1:8000/graphql/")
DB_URL = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")
STAFF_EMAIL = os.getenv("STAFF_USER", os.getenv("STAFF_EMAIL", "admin@example.com"))
STAFF_PASSWORD = os.getenv("STAFF_PASSWORD", "admin")


def staff_login(page: Page) -> None:
    """Helper to perform staff login into Saleor Dashboard using role-based locators."""
    page.goto(DASHBOARD_URL)
    page.get_by_role("textbox", name="Email").fill(STAFF_EMAIL)
    page.get_by_role("textbox", name="Password").fill(STAFF_PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle")


def create_paid_unfulfilled_order(
    quantity: int = 2,
    customer_email: str = "ui_test_buyer@example.com",
) -> tuple[str, str, int, float]:
    """Create a fresh paid and unfulfilled order via Saleor GraphQL API.

    Returns (raw_uuid, relay_id, order_number, unit_price).
    """
    client = SaleorGraphQLClient(base_url=API_URL)

    # 1. Obtain staff JWT token
    token_resp = client.execute(
        """
        mutation TokenCreate($email: String!, $password: String!) {
          tokenCreate(email: $email, password: $password) {
            token
          }
        }
        """,
        {"email": STAFF_EMAIL, "password": STAFF_PASSWORD},
    )
    token = token_resp["tokenCreate"]["token"]

    # 2. Retrieve digital variant and channel IDs from database
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.id, cl.price_amount
            FROM product_productvariant v
            JOIN product_product p ON p.id = v.product_id
            JOIN product_producttype pt ON pt.id = p.product_type_id
            JOIN product_productvariantchannellisting cl ON cl.variant_id = v.id
            JOIN channel_channel ch ON ch.id = cl.channel_id
            WHERE ch.slug = 'default-channel' AND pt.is_shipping_required = false
            LIMIT 1
            """
        )
        row_v = cur.fetchone()
        assert row_v is not None, "No digital variant found in database"
        v_id, unit_price = row_v[0], float(row_v[1])

        cur.execute("SELECT id FROM channel_channel WHERE slug = 'default-channel'")
        row_ch = cur.fetchone()
        assert row_ch is not None, "Default channel not found in database"
        ch_id = row_ch[0]

    v_relay = base64.b64encode(f"ProductVariant:{v_id}".encode()).decode()
    ch_relay = base64.b64encode(f"Channel:{ch_id}".encode()).decode()

    # 3. Create Draft Order
    draft = client.execute(
        """
        mutation DraftCreate($channel: ID!, $email: String!) {
          draftOrderCreate(input: {
            channelId: $channel,
            userEmail: $email,
            billingAddress: {
              firstName: "Jane",
              lastName: "Doe",
              streetAddress1: "100 Broadway",
              city: "New York",
              postalCode: "10001",
              country: US,
              countryArea: "NY"
            }
          }) {
            order { id number status }
            errors { field message code }
          }
        }
        """,
        {"channel": ch_relay, "email": customer_email},
        token=token,
    )
    assert not draft["draftOrderCreate"]["errors"], draft["draftOrderCreate"]["errors"]
    order_id = draft["draftOrderCreate"]["order"]["id"]

    # 4. Add order lines
    lines = client.execute(
        """
        mutation AddLines($id: ID!, $lines: [OrderLineCreateInput!]!) {
          orderLinesCreate(id: $id, input: $lines) {
            order { id }
            errors { field message code }
          }
        }
        """,
        {"id": order_id, "lines": [{"variantId": v_relay, "quantity": quantity}]},
        token=token,
    )
    assert not lines["orderLinesCreate"]["errors"], lines["orderLinesCreate"]["errors"]

    # 5. Complete Draft Order to UNFULFILLED
    complete = client.execute(
        """
        mutation Complete($id: ID!) {
          draftOrderComplete(id: $id) {
            order { id number status }
            errors { field message code }
          }
        }
        """,
        {"id": order_id},
        token=token,
    )
    assert not complete["draftOrderComplete"]["errors"], complete["draftOrderComplete"]["errors"]
    completed_order = complete["draftOrderComplete"]["order"]
    order_number = int(completed_order["number"])

    # 6. Mark order as paid
    paid = client.execute(
        """
        mutation MarkPaid($id: ID!) {
          orderMarkAsPaid(id: $id) {
            order { id status paymentStatus }
            errors { field message code }
          }
        }
        """,
        {"id": order_id},
        token=token,
    )

    assert not paid["orderMarkAsPaid"]["errors"], paid["orderMarkAsPaid"]["errors"]

    raw_uuid = base64.b64decode(order_id).decode().split(":")[-1]
    return raw_uuid, order_id, order_number, unit_price


@pytest.mark.req("REQ-UI-001")
def test_01_staff_login(page: Page) -> None:
    """1. Staff member logs into Saleor Dashboard using valid credentials from environment."""
    staff_login(page)
    expect(page.get_by_role("link", name="Catalog")).to_be_visible()
    expect(page.get_by_role("link", name="Customers")).to_be_visible()


@pytest.mark.req("REQ-UI-001")
def test_02_find_order(page: Page) -> None:
    """2. Staff member navigates to orders and inspects a newly created order."""
    raw_id, relay_id, number, _ = create_paid_unfulfilled_order()
    staff_login(page)

    encoded_relay_id = urllib.parse.quote(relay_id)
    page.goto(f"{DASHBOARD_URL}/dashboard/orders/{encoded_relay_id}")
    page.wait_for_load_state("networkidle")

    # Verify order number is displayed in header
    expect(page.get_by_text(f"Order #{number}")).to_be_visible()

    # Verify initial status via API
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM order_order WHERE id = %s", (raw_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "unfulfilled", f"Expected initial status 'unfulfilled', got {row[0]}"


@pytest.mark.req("REQ-UI-001")
def test_03_fulfill_order(page: Page) -> None:
    """3. Staff member performs fulfillment on an unfulfilled order through UI."""
    raw_id, relay_id, number, _ = create_paid_unfulfilled_order()
    staff_login(page)

    encoded_relay_id = urllib.parse.quote(relay_id)
    page.goto(f"{DASHBOARD_URL}/dashboard/orders/{encoded_relay_id}")
    page.wait_for_load_state("networkidle")

    # Step must not have conditional fallback: clicking Fulfill must navigate to fulfill form
    page.get_by_role("button", name="Fulfill").click()
    page.wait_for_load_state("networkidle")

    # On fulfillment configuration page, confirm fulfillment
    page.get_by_role("button", name="Fulfill").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Assert exact result via API / database: status MUST be 'fulfilled'
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM order_order WHERE id = %s", (raw_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "fulfilled", f"Expected order {number} to be 'fulfilled', got '{row[0]}'"


@pytest.mark.req("REQ-UI-001")
def test_04_issue_partial_refund(page: Page) -> None:
    """4. Staff member issues a partial refund through the dashboard interface."""
    raw_id, relay_id, _, unit_price = create_paid_unfulfilled_order(quantity=2)
    staff_login(page)

    encoded_relay_id = urllib.parse.quote(relay_id)
    page.goto(f"{DASHBOARD_URL}/dashboard/orders/{encoded_relay_id}/payment-refund")
    page.wait_for_load_state("networkidle")

    # Fill quantity for first refundable product (1 unit out of 2)
    page.get_by_role("spinbutton").first.fill("1")
    page.wait_for_timeout(300)

    # Click Refund button (no conditional fallback)
    page.get_by_role("button", name="Refund").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Assert exact refunded amount via database
    expected_refund = unit_price * 1.0
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT parameters
            FROM order_orderevent
            WHERE order_id = %s AND type = 'payment_refunded'
            ORDER BY id DESC LIMIT 1
            """,
            (raw_id,),
        )
        row = cur.fetchone()
        assert row is not None, f"No payment_refunded event recorded for order {raw_id}"
        event_params = row[0]
        actual_refund = float(event_params.get("amount", 0.0))
        assert actual_refund == pytest.approx(expected_refund, rel=1e-2), (
            f"Expected refund {expected_refund}, got {actual_refund}"
        )


@pytest.mark.req("REQ-UI-001")
def test_05_see_refund_in_order_history(page: Page) -> None:
    """5. Staff member verifies the refund is visible in order history/timeline."""
    raw_id, relay_id, _, _unit_price = create_paid_unfulfilled_order(quantity=2)
    staff_login(page)

    encoded_relay_id = urllib.parse.quote(relay_id)
    page.goto(f"{DASHBOARD_URL}/dashboard/orders/{encoded_relay_id}/payment-refund")
    page.wait_for_load_state("networkidle")

    page.get_by_role("spinbutton").first.fill("1")
    page.wait_for_timeout(300)
    page.get_by_role("button", name="Refund").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Navigate to order detail page
    page.goto(f"{DASHBOARD_URL}/dashboard/orders/{encoded_relay_id}")
    page.wait_for_load_state("networkidle")

    # Assert refund indicators are visible in order timeline via role/text locators
    expect(page.get_by_text("Order History")).to_be_visible()
    expect(page.get_by_text("Payment was refunded")).to_be_visible()

    # Verify exact refund event in order history via API / database
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT type, parameters
            FROM order_orderevent
            WHERE order_id = %s AND type IN ('payment_refunded', 'fulfillment_refunded')
            ORDER BY id
            """,
            (raw_id,),
        )
        events = cur.fetchall()
        assert len(events) >= 1, f"Expected refund events in history, found none for order {raw_id}"
        event_types = [e[0] for e in events]
        assert "payment_refunded" in event_types, f"Missing payment_refunded in {event_types}"
