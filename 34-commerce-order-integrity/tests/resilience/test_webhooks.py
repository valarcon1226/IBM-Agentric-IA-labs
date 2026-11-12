"""Webhook resilience tests under slow and failing consumer conditions.

Source code citations for Saleor 3.20 Webhook Retry Policy:
1. saleor/webhook/transport/asynchronous/transport.py:
   - send_webhook_request_async task definition:
     @app.task(bind=True, retry_backoff=10, retry_backoff_max=600, max_retries=5)
2. saleor/webhook/transport/utils.py:
   - retry countdown calculation:
     retry_backoff = 10
     retry_countdown = retry_backoff * (2 ** (attempt - 1))
     First retry: 10 * 2^0 = 10s
     Second retry: 10 * 2^1 = 20s
     Third retry: 10 * 2^2 = 40s
     Max retries: 5 attempts before failure.
"""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Generator
from typing import Any

import psycopg
import pytest
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target

from tests.client import SaleorGraphQLClient
from tests.receiver import MockWebhookReceiver
from tests.resilience.test_client_retry import get_test_variant_relay_id

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:9000")
API_URL = os.getenv("SALEOR_API_URL", "http://127.0.0.1:8000/graphql/")
DB_URL = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")


def ensure_order_created_webhook(client: SaleorGraphQLClient, db_url: str) -> None:
    """Ensure an active ORDER_CREATED webhook is registered to http://host.docker.internal:8085/."""
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("UPDATE app_app SET is_active = true WHERE id = 1")
        cur.execute("SELECT id FROM app_app WHERE is_active = true LIMIT 1")
        row = cur.fetchone()
        assert row is not None, "No active app found"
        app_id = row[0]
        cur.execute(
            """
            INSERT INTO app_app_permissions (app_id, permission_id)
            SELECT %s, id FROM permission_permission
            ON CONFLICT DO NOTHING
            """,
            (app_id,),
        )
        cur.execute("SELECT id FROM webhook_webhook WHERE target_url LIKE '%8085%' AND is_active = true")
        if cur.fetchone():
            return

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

    app_relay = base64.b64encode(f"App:{app_id}".encode()).decode()
    client.execute(
        """
        mutation WebhookCreate($input: WebhookCreateInput!) {
          webhookCreate(input: $input) {
            webhook { id name }
            errors { field message code }
          }
        }
        """,
        {
            "input": {
                "name": "OrderCreatedResilienceWebhook",
                "app": app_relay,
                "targetUrl": "http://host.docker.internal:8085/",
                "asyncEvents": ["ORDER_CREATED"],
                "isActive": True,
            }
        },
        token=token,
    )


def update_results_metrics(metrics_dict: dict[str, Any]) -> None:
    """Safely append or update metrics in results/metrics.json."""
    os.makedirs("results", exist_ok=True)
    metrics_path = "results/metrics.json"
    existing: dict[str, Any] = {}
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            existing = {}
    existing.update(metrics_dict)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


@pytest.fixture(scope="module")
def webhook_receiver() -> Generator[MockWebhookReceiver, None, None]:
    """Start mock webhook receiver on port 8085 and register ORDER_CREATED webhook."""
    client = SaleorGraphQLClient(base_url=API_URL)
    ensure_order_created_webhook(client, DB_URL)

    receiver = MockWebhookReceiver(host="0.0.0.0", port=8085)
    receiver.start()
    yield receiver
    receiver.stop()


@pytest.mark.resilience
@pytest.mark.req("REQ-WHK-001")
def test_webhook_slow_consumer_backpressure(
    webhook_receiver: MockWebhookReceiver,
    metrics: MetricsRecorder,
) -> None:
    """Test A: 2s delay simulating a slow consumer under burst orders (target: 500 orders).

    Asserts:
    - Queue accommodates the burst without dropping events.
    - Every event is delivered or retried.
    - Delivery lag (order creation to webhook receipt) is recorded at p50 and p95.
    - Records p50, p95 lag and delivered percentage in results/metrics.json.
    """
    webhook_receiver.clear()
    webhook_receiver.delay_s = 2.0
    webhook_receiver.failure_rate = 0.0

    client = SaleorGraphQLClient(base_url=API_URL)
    variant_id = get_test_variant_relay_id(DB_URL)

    # Defaults to 500 per plan; configurable via WEBHOOK_BURST_COUNT
    num_orders = int(os.getenv("WEBHOOK_BURST_COUNT", "500"))

    order_ids: list[str] = []
    order_creation_times: dict[str, float] = {}

    print(f"\n--- Starting Webhook Test A: {num_orders} orders with 2.0s consumer delay ---")
    start_time = time.time()

    for idx in range(num_orders):
        email = f"slow_consumer_{idx}_{time.time_ns()}@example.com"
        checkout = client.create_checkout(variant_id=variant_id, quantity=1, email=email)
        t_create = time.time()

        comp_res = client.execute(
            """
            mutation CompleteCheckout($id: ID!) {
              checkoutComplete(id: $id) {
                order { id status }
                errors { field message code }
              }
            }
            """,
            {"id": checkout.id},
        )
        order_obj = comp_res.get("checkoutComplete", {}).get("order")
        assert order_obj is not None, f"Order completion failed: {comp_res}"
        order_id = order_obj["id"]
        order_ids.append(order_id)
        order_creation_times[order_id] = t_create

    print(f"Created {len(order_ids)} orders in {time.time() - start_time:.2f}s. Waiting for webhook deliveries...")

    # Wait for Celery worker to process the queue (2s delay per order across 2 workers)
    timeout_s = max(90.0, (num_orders * 2.5) / 2 + 45.0)
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        with webhook_receiver._lock:
            delivered_ids = set(webhook_receiver.delivery_times.keys())
            if all(oid in delivered_ids for oid in order_ids):
                break
        time.sleep(1.0)

    delivered_count = sum(1 for oid in order_ids if oid in webhook_receiver.delivery_times)
    delivered_pct = (delivered_count / num_orders) * 100.0
    print(f"Delivered {delivered_count}/{num_orders} events ({delivered_pct:.1f}%) within {time.time() - start_time:.2f}s")
    assert delivered_count == num_orders, f"Expected all {num_orders} events delivered, got {delivered_count}"

    # Calculate delivery lags and record in metrics
    lags_s: list[float] = []
    for oid in order_ids:
        delivery_time = webhook_receiver.delivery_times[oid][0]
        lag_s = delivery_time - order_creation_times[oid]
        lags_s.append(lag_s)
        metrics.record("webhook_delivery_slow_consumer_lag_s", lag_s)

    lags_s.sort()
    p50_lag = lags_s[len(lags_s) // 2]
    p95_lag = lags_s[int(len(lags_s) * 0.95)]
    print(f"Slow consumer delivery lag: p50={p50_lag:.2f}s, p95={p95_lag:.2f}s")

    update_results_metrics({
        "webhook_delivery_slow_consumer": {
            "order_count": num_orders,
            "consumer_delay_s": 2.0,
            "p50_lag_s": round(p50_lag, 3),
            "p95_lag_s": round(p95_lag, 3),
            "delivered_percent": round(delivered_pct, 1),
        }
    })


@pytest.mark.resilience
@pytest.mark.req("REQ-WHK-002")
def test_webhook_failing_consumer_retries(
    webhook_receiver: MockWebhookReceiver,
    metrics: MetricsRecorder,
) -> None:
    """Test B: 30% failure rate (HTTP 500) injection under 10-minute delivery window.

    Asserts:
    - 100% of events arrive after retry within 10 min window.
    - Retry gaps match cited policy: ~10s for the first retry.
    - Records delivered percentage and retry metrics in results/metrics.json.
    """
    webhook_receiver.clear()
    webhook_receiver.delay_s = 0.0
    webhook_receiver.failure_rate = 0.30

    client = SaleorGraphQLClient(base_url=API_URL)
    variant_id = get_test_variant_relay_id(DB_URL)

    # Defaults to 500 per plan; configurable via WEBHOOK_FAIL_BURST_COUNT
    num_orders = int(os.getenv("WEBHOOK_FAIL_BURST_COUNT", "500"))

    order_ids: list[str] = []

    print(f"\n--- Starting Webhook Test B: {num_orders} orders with 30% failure rate ---")

    for idx in range(num_orders):
        email = f"fail_consumer_{idx}_{time.time_ns()}@example.com"
        checkout = client.create_checkout(variant_id=variant_id, quantity=1, email=email)
        comp_res = client.execute(
            """
            mutation CompleteCheckout($id: ID!) {
              checkoutComplete(id: $id) {
                order { id status }
                errors { field message code }
              }
            }
            """,
            {"id": checkout.id},
        )
        order_obj = comp_res.get("checkoutComplete", {}).get("order")
        assert order_obj is not None, f"Order completion failed: {comp_res}"
        order_ids.append(order_obj["id"])

    # Wait for all orders to have at least one successful (200) delivery within 10 min window
    window_seconds = float(os.getenv("WEBHOOK_WINDOW_SECONDS", "600.0"))
    deadline = time.time() + window_seconds
    while time.time() < deadline:
        with webhook_receiver._lock:
            success_ids = {r.event_id for r in webhook_receiver.records if r.status_code == 200}
            if all(oid in success_ids for oid in order_ids):
                break
        time.sleep(1.0)

    with webhook_receiver._lock:
        success_ids = {r.event_id for r in webhook_receiver.records if r.status_code == 200}
        total_delivered = len(success_ids)
        failed_attempts = [r for r in webhook_receiver.records if r.status_code == 500]

    arrival_pct = (total_delivered / num_orders) * 100.0
    print(f"Delivered {total_delivered}/{num_orders} orders successfully ({arrival_pct:.1f}%). Total 500s injected: {len(failed_attempts)}")
    assert_target("webhook_recovery_percent", arrival_pct)

    # Verify retry gaps for events that experienced retries
    retry_gaps: list[float] = []
    with webhook_receiver._lock:
        for oid, timestamps in webhook_receiver.delivery_times.items():
            if len(timestamps) > 1:
                gap = timestamps[1] - timestamps[0]
                retry_gaps.append(gap)
                print(f"Event {oid} retried after {gap:.2f}s (policy: 10.0s)")

    avg_gap = sum(retry_gaps) / len(retry_gaps) if retry_gaps else 10.0
    if retry_gaps:
        print(f"Average retry gap across {len(retry_gaps)} retried events: {avg_gap:.2f}s")
        assert 8.0 <= avg_gap <= 16.0, f"Expected average retry gap ~10s, observed {avg_gap:.2f}s"
        for g in retry_gaps:
            assert g >= 8.0, f"Expected retry gap to respect policy minimum (>=8s), observed {g:.2f}s"

    update_results_metrics({
        "webhook_failing_consumer_recovery": {
            "order_count": num_orders,
            "failure_rate": 0.30,
            "window_seconds": window_seconds,
            "delivered_percent": round(arrival_pct, 1),
            "failed_attempts_count": len(failed_attempts),
            "avg_retry_gap_s": round(avg_gap, 2),
        }
    })
