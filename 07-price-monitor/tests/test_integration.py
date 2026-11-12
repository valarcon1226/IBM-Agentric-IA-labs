"""Integration tests running against the Docker compose stack."""

import os
import urllib.error
import urllib.request
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8007")
API_TOKEN = os.environ.get("E2E_API_TOKEN", "change_me_api_token")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


@pytest.fixture(scope="module")
def compose_stack() -> str:
    try:
        with urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=3) as resp:
            if resp.status != 200:
                pytest.skip(f"Docker stack not healthy at {API_BASE_URL}: HTTP {resp.status}")
    except Exception as exc:
        pytest.skip(f"Docker stack not reachable at {API_BASE_URL}: {exc}")
    return API_BASE_URL


def test_stack_health(compose_stack: str):
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(f"{compose_stack}/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


def test_integration_flow_with_demo_product(compose_stack: str):
    unique_suffix = uuid.uuid4().hex[:6]
    product_payload = {
        "name": f"Integration Keyboard {unique_suffix}",
        "url": f"http://demo-store/products/keyboard.html?test={unique_suffix}",
        "site_domain": "demo-store",
        "target_price": 100.00,
        "alert_threshold_pct": 5.0,
        "currency": "USD",
        "check_interval_hours": 6,
        "requires_js": False,
        "is_active": True,
    }

    product_id = None
    with httpx.Client(timeout=10.0) as client:
        try:
            # 1. Register product
            create_resp = client.post(
                f"{compose_stack}/api/v1/products/",
                json=product_payload,
                headers=HEADERS,
            )
            assert create_resp.status_code == 201, create_resp.text
            product_id = create_resp.json()["id"]

            # 2. Force scrape
            scrape_resp = client.post(
                f"{compose_stack}/api/v1/products/{product_id}/scrape",
                headers=HEADERS,
            )
            assert scrape_resp.status_code == 200, scrape_resp.text
            scrape_data = scrape_resp.json()
            assert scrape_data["status"] == "SUCCESS"
            assert scrape_data["new_price"] == 120.0

            # 3. Check history
            history_resp = client.get(
                f"{compose_stack}/api/v1/products/{product_id}/history",
                headers=HEADERS,
            )
            assert history_resp.status_code == 200
            history_items = history_resp.json()
            assert len(history_items) >= 1
            assert float(history_items[0]["price"]) == 120.0

            # 4. Check CSV export
            export_resp = client.get(
                f"{compose_stack}/api/v1/export/csv?product_id={product_id}",
                headers=HEADERS,
            )
            assert export_resp.status_code == 200
            assert "text/csv" in export_resp.headers["content-type"]
            assert "Integration Keyboard" in export_resp.text

        finally:
            # Cleanup
            if product_id:
                client.delete(f"{compose_stack}/api/v1/products/{product_id}", headers=HEADERS)
