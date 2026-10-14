"""Pruebas de cambio de estado de pedidos y disparador de notificaciones."""

import pytest

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
from app.security import create_csrf_token


@pytest.fixture
def existing_order():
    """Inserta un pedido base en estado listo_para_despachar."""
    order = Order(
        id="ORD-TEST-001",
        external_id="ext_999",
        source=OrderSource.SHOPIFY,
        status=OrderStatus.LISTO_PARA_DESPACHAR,
        payment_status=PaymentStatus.PAID,
        customer=Customer(
            name="Laura Restrepo",
            email="laura@example.com",
            phone="+573112223344",
            shipping_address=ShippingAddress(
                street="Calle 45 # 13-20",
                city="Cali",
                state="Valle",
            ),
        ),
        items=[
            OrderItem(
                sku="CF-HUI-250",
                title="Café Huila Especial (250g)",
                quantity=1,
                unit_price=28000.0,
                total_price=28000.0,
            )
        ],
        total_amount=28000.0,
        currency="COP",
    )
    return order


def test_transition_to_despachado(authenticated_client, existing_order):
    """Verifica que un pedido pase a 'despachado' y se registre en el historial."""
    repo = get_repository()
    import asyncio

    asyncio.run(repo.create_order(existing_order))

    csrf_token = create_csrf_token(settings.ADMIN_USERNAME, settings.SECRET_KEY)

    response = authenticated_client.post(
        f"/admin/orders/{existing_order.id}/status",
        data={
            "new_status": "despachado",
            "note": "Guía Coordinadora 998877",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 303

    updated = asyncio.run(repo.get_order(existing_order.id))
    assert updated.status == OrderStatus.DESPACHADO
    assert len(updated.history) >= 1
    assert updated.history[-1].to_status == "despachado"
    assert "998877" in updated.history[-1].note


def test_transition_to_entregado(authenticated_client, existing_order):
    """Verifica que un pedido despachado pueda marcarse como 'entregado'."""
    repo = get_repository()
    import asyncio

    existing_order.status = OrderStatus.DESPACHADO
    asyncio.run(repo.create_order(existing_order))

    csrf_token = create_csrf_token(settings.ADMIN_USERNAME, settings.SECRET_KEY)

    response = authenticated_client.post(
        f"/admin/orders/{existing_order.id}/status",
        data={
            "new_status": "entregado",
            "note": "Entregado a la portera del edificio",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 303

    updated = asyncio.run(repo.get_order(existing_order.id))
    assert updated.status == OrderStatus.ENTREGADO


def test_invalid_status_rejected(authenticated_client, existing_order):
    """Verifica que un estado no contemplado en el enum sea rechazado con 400."""
    repo = get_repository()
    import asyncio

    asyncio.run(repo.create_order(existing_order))

    csrf_token = create_csrf_token(settings.ADMIN_USERNAME, settings.SECRET_KEY)

    response = authenticated_client.post(
        f"/admin/orders/{existing_order.id}/status",
        data={
            "new_status": "estado_inventado_invalido",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 400
