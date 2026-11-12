"""Locust load test for Saleor product listing, checkout create, and checkout complete.

Target SLAs (targets.toml):
- products(first: 100) query, p95 <= 400 ms
- Checkout create -> complete, p95 <= 1500 ms at 10 concurrent clients
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any

import psycopg
from locust import HttpUser, between, events, task


def get_available_variant_id() -> str:
    """Retrieve an existing product variant relay ID with ample stock."""
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT pv.id
            FROM product_productvariant pv
            JOIN warehouse_stock ws ON ws.product_variant_id = pv.id
            WHERE ws.quantity > 50
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            import base64
            return base64.b64encode(f"ProductVariant:{row[0]}".encode()).decode()
        return "UHJvZHVjdFZhcmlhbnQ6NDAz"


VARIANT_RELAY_ID = get_available_variant_id()


class SaleorBuyerUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(3)
    def list_products(self) -> None:
        """Query product catalog (first: 100)."""
        query = """
        query ListProducts {
          products(first: 100, channel: "default-channel") {
            edges {
              node {
                id
                name
                slug
              }
            }
          }
        }
        """
        self.client.post(
            "/graphql/",
            json={"query": query},
            name="products_query_100",
        )

    @task(1)
    def checkout_lifecycle(self) -> None:
        """Full buyer flow: create checkout and complete checkout."""
        t_start = time.time()
        email = f"load_{random.randint(1000, 999999)}_{time.time_ns()}@example.com"
        create_mutation = """
        mutation CreateCheckout($lines: [CheckoutLineInput!]!, $email: String!) {
          checkoutCreate(input: { channel: "default-channel", lines: $lines, email: $email }) {
            checkout { id }
            errors { field message code }
          }
        }
        """
        res_create = self.client.post(
            "/graphql/",
            json={
                "query": create_mutation,
                "variables": {
                    "lines": [{"quantity": 1, "variantId": VARIANT_RELAY_ID}],
                    "email": email,
                },
            },
            name="checkout_create",
        )
        if res_create.status_code != 200:
            return

        data = res_create.json().get("data", {}).get("checkoutCreate", {})
        checkout = data.get("checkout")
        if not checkout or not checkout.get("id"):
            return

        checkout_id = checkout["id"]
        complete_mutation = """
        mutation CompleteCheckout($id: ID!) {
          checkoutComplete(id: $id) {
            order { id status }
            errors { field message code }
          }
        }
        """
        self.client.post(
            "/graphql/",
            json={"query": complete_mutation, "variables": {"id": checkout_id}},
            name="checkout_complete",
        )
        total_checkout_ms = (time.time() - t_start) * 1000.0
        events.request.fire(
            request_type="custom",
            name="checkout_create_to_complete",
            response_time=total_checkout_ms,
            response_length=0,
            exception=None,
            context={},
        )


@events.test_stop.add_listener
def on_test_stop(environment: Any, **kwargs: Any) -> None:
    """Save metrics to results/metrics.json upon test completion."""
    os.makedirs("results", exist_ok=True)
    metrics_path = "results/metrics.json"

    current_metrics: dict[str, Any] = {}
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, encoding="utf-8") as f:
                current_metrics = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            current_metrics = {}

    stats = environment.runner.stats
    for name in ["products_query_100", "checkout_create_to_complete"]:
        entry = stats.get(name, "POST") if name == "products_query_100" else stats.get(name, "custom")
        if entry and entry.num_requests > 0:
            current_metrics[name] = {
                "count": entry.num_requests,
                "p50_ms": entry.get_response_time_percentile(0.50),
                "p95_ms": entry.get_response_time_percentile(0.95),
                "p99_ms": entry.get_response_time_percentile(0.99),
                "avg_ms": round(entry.avg_response_time, 2),
                "errors": entry.num_failures,
            }

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(current_metrics, f, indent=2)
    print(f"\nLocust performance metrics written to {metrics_path}")
