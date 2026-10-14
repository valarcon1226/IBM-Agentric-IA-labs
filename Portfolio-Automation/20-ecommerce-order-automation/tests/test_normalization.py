"""Pruebas de normalización de pedidos dispares a modelo único Order."""

import json

from app.models import OrderSource, OrderStatus, PaymentStatus
from app.normalizers import (
    normalize_shopify_order,
    normalize_stripe_payment_intent,
    normalize_woocommerce_order,
)


def test_normalize_woocommerce(sample_payloads):
    """Verifica que un payload de WooCommerce se convierta a un objeto Order normalizado."""
    payload = json.loads(sample_payloads["wc_bytes"].decode("utf-8"))
    order = normalize_woocommerce_order(payload)

    assert order.id == "ORD-WC-501"
    assert order.external_id == "501"
    assert order.source == OrderSource.WOOCOMMERCE
    assert order.status == OrderStatus.LISTO_PARA_DESPACHAR
    assert order.payment_status == PaymentStatus.PAID

    # Cliente
    assert order.customer.name == "Valentina Alarcón"
    assert order.customer.email == "valentina.alarcon@example.com"
    assert order.customer.phone == "+573001234567"
    assert "Carrera 7" in order.customer.shipping_address.street
    assert order.customer.shipping_address.city == "Bogotá"

    # Items y totales
    assert len(order.items) == 2
    assert order.items[0].sku == "CF-HUI-250"
    assert order.items[0].quantity == 2
    assert order.items[1].sku == "CF-NAR-250"
    assert order.total_amount == 86000.0
    assert order.currency == "COP"


def test_normalize_shopify(sample_payloads):
    """Verifica que un payload de Shopify se convierta a un objeto Order normalizado."""
    payload = json.loads(sample_payloads["shopify_bytes"].decode("utf-8"))
    order = normalize_shopify_order(payload)

    assert order.id == "ORD-SHP-1042"
    assert order.external_id == "1042"
    assert order.source == OrderSource.SHOPIFY
    assert order.status == OrderStatus.LISTO_PARA_DESPACHAR
    assert order.payment_status == PaymentStatus.PAID

    # Cliente
    assert order.customer.name == "Carlos Mendoza"
    assert order.customer.email == "carlos.mendoza@example.com"
    assert order.customer.phone == "+573159876543"
    assert "Calle 10" in order.customer.shipping_address.street
    assert order.customer.shipping_address.city == "Medellín"

    # Items y totales
    assert len(order.items) == 1
    assert order.items[0].sku == "CF-GEI-250"
    assert order.items[0].quantity == 1
    assert order.total_amount == 55000.0


def test_normalize_stripe(sample_payloads):
    """Verifica que un payment_intent.succeeded de Stripe se convierta a un Order normalizado."""
    payload = json.loads(sample_payloads["stripe_bytes"].decode("utf-8"))
    order = normalize_stripe_payment_intent(payload)

    assert "ORD-STP-" in order.id
    assert "pi_3P8xYz" in order.external_id
    assert order.source == OrderSource.STRIPE
    assert order.status == OrderStatus.LISTO_PARA_DESPACHAR
    assert order.payment_status == PaymentStatus.PAID

    # Cliente desde metadata
    assert order.customer.name == "Andrea Gómez"
    assert order.customer.email == "andrea.gomez@example.com"
    assert "Avenida El Poblado" in order.customer.shipping_address.street
    assert order.customer.shipping_address.city == "Medellín"

    # Items
    assert len(order.items) == 1
    assert order.items[0].sku == "CF-HUI-250"
    assert order.items[0].quantity == 3
    assert order.total_amount == 84000.0
