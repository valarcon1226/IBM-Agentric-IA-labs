"""Pruebas de protección contra ataques CSRF (Cross-Site Request Forgery)."""

import asyncio

from app.config import settings
from app.database import get_repository
from app.models import (
    Customer,
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    PaymentStatus,
    ShippingAddress,
)


def test_login_missing_csrf(client):
    """El formulario de login sin token CSRF debe retornar 400."""
    response = client.post(
        "/admin/login",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 422 or response.status_code == 400


def test_login_invalid_csrf(client):
    """El formulario de login con token CSRF inválido debe retornar 400."""
    response = client.post(
        "/admin/login",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
            "csrf_token": "token_csrf_completamente_falso_y_vencido",
        },
    )
    assert response.status_code == 400
    assert "csrf" in response.text.lower()


def test_status_update_missing_csrf(authenticated_client):
    """La actualización de estado de un pedido sin token CSRF debe ser rechazada."""
    order = Order(
        id="ORD-CSRF-001",
        external_id="ext_csrf",
        source=OrderSource.WOOCOMMERCE,
        status=OrderStatus.LISTO_PARA_DESPACHAR,
        payment_status=PaymentStatus.PAID,
        customer=Customer(
            name="Test", email="test@example.com", shipping_address=ShippingAddress()
        ),
        items=[OrderItem(sku="SKU", title="Item", quantity=1, unit_price=10.0, total_price=10.0)],
        total_amount=10.0,
    )
    repo = get_repository()
    asyncio.run(repo.create_order(order))

    response = authenticated_client.post(
        f"/admin/orders/{order.id}/status",
        data={"new_status": "despachado"},
    )
    assert response.status_code == 422 or response.status_code == 400


def test_status_update_invalid_csrf(authenticated_client):
    """La actualización con token CSRF inválido debe responder 400."""
    order = Order(
        id="ORD-CSRF-002",
        external_id="ext_csrf2",
        source=OrderSource.WOOCOMMERCE,
        status=OrderStatus.LISTO_PARA_DESPACHAR,
        payment_status=PaymentStatus.PAID,
        customer=Customer(
            name="Test", email="test@example.com", shipping_address=ShippingAddress()
        ),
        items=[OrderItem(sku="SKU", title="Item", quantity=1, unit_price=10.0, total_price=10.0)],
        total_amount=10.0,
    )
    repo = get_repository()
    asyncio.run(repo.create_order(order))

    response = authenticated_client.post(
        f"/admin/orders/{order.id}/status",
        data={
            "new_status": "despachado",
            "csrf_token": "csrf_falso_12345",
        },
    )
    assert response.status_code == 400
    assert "csrf" in response.json()["detail"].lower()
