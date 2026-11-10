"""Unit tests for FastAPI endpoints: authentication, CRUD, and CSV export."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_async_session
from app.api.main import app
from app.db.models import Product


def test_health_healthy(client: TestClient):
    mock_session = AsyncMock()
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}
    finally:
        app.dependency_overrides.clear()


def test_health_unhealthy_returns_503(client: TestClient):
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB offline")
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"
    finally:
        app.dependency_overrides.clear()


def test_auth_missing_token_returns_401(client: TestClient):
    resp = client.get("/api/v1/products/")
    assert resp.status_code == 401


def test_auth_invalid_token_returns_401(client: TestClient):
    resp = client.get("/api/v1/products/", headers={"Authorization": "Bearer wrong_token"})
    assert resp.status_code == 401


def test_create_product(client: TestClient, auth_headers: dict[str, str]):
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.scalar.return_value = None  # No duplicate URL

    now = datetime.now(UTC)
    product_id = uuid.uuid4()

    def fake_refresh(obj):
        obj.id = product_id
        obj.created_at = now
        obj.updated_at = now

    mock_session.refresh.side_effect = fake_refresh
    app.dependency_overrides[get_async_session] = lambda: mock_session

    payload = {
        "name": "Mechanical Keyboard RGB",
        "url": "http://demo-store/products/keyboard.html",
        "site_domain": "demo-store",
        "target_price": 100.00,
        "alert_threshold_pct": 5.0,
        "currency": "USD",
        "check_interval_hours": 6,
        "requires_js": False,
        "is_active": True,
    }

    try:
        resp = client.post("/api/v1/products/", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Mechanical Keyboard RGB"
        assert data["url"] == "http://demo-store/products/keyboard.html"
        assert float(data["target_price"]) == 100.00
    finally:
        app.dependency_overrides.clear()


def test_list_products(client: TestClient, auth_headers: dict[str, str]):
    now = datetime.now(UTC)
    p = Product(
        id=uuid.uuid4(),
        name="Studio Headphones",
        url="http://demo-store/products/headphones.html",
        site_domain="demo-store",
        target_price=Decimal("70.00"),
        alert_threshold_pct=Decimal("5.00"),
        alert_threshold_abs=Decimal("0.00"),
        currency="USD",
        check_interval_hours=6,
        requires_js=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [p]
    mock_session.scalars.return_value = mock_result

    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        resp = client.get("/api/v1/products/", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "Studio Headphones"
    finally:
        app.dependency_overrides.clear()


def test_get_product_not_found(client: TestClient, auth_headers: dict[str, str]):
    mock_session = AsyncMock()
    mock_session.get.return_value = None
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        resp = client.get(f"/api/v1/products/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_product(client: TestClient, auth_headers: dict[str, str]):
    p = Product(
        id=uuid.uuid4(),
        name="To Delete",
        url="http://demo-store/delete.html",
        site_domain="demo-store",
    )
    mock_session = AsyncMock()
    mock_session.get.return_value = p
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        resp = client.delete(f"/api/v1/products/{p.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Product deleted successfully."
        mock_session.delete.assert_called_once_with(p)
    finally:
        app.dependency_overrides.clear()


def test_export_csv(client: TestClient, auth_headers: dict[str, str]):
    mock_session = AsyncMock()
    mock_row = MagicMock()
    mock_row.scraped_at = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)
    mock_row.product_id = uuid.uuid4()
    mock_row.product_name = "Mechanical Keyboard RGB"
    mock_row.url = "http://demo-store/products/keyboard.html"
    mock_row.price = Decimal("120.00")
    mock_row.currency = "USD"
    mock_row.availability = True

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        resp = client.get("/api/v1/export/csv", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "scraped_at,product_id,product_name,url,price,currency,availability" in content
        assert "Mechanical Keyboard RGB" in content
        assert "120.00" in content
    finally:
        app.dependency_overrides.clear()
