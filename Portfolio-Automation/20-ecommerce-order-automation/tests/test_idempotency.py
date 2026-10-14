"""Pruebas de idempotencia en la ingesta de webhooks para evitar duplicación de pedidos."""

from app.config import settings
from samples.send_webhooks import sign_shopify, sign_stripe, sign_woocommerce


def test_woocommerce_idempotency(client, sample_payloads):
    """Verifica que el reenvío de un webhook de WooCommerce no cree un pedido duplicado."""
    payload = sample_payloads["wc_bytes"]
    headers = sign_woocommerce(payload, settings.WOOCOMMERCE_WEBHOOK_SECRET)

    # Primer envío
    res1 = client.post("/webhooks/woocommerce", content=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    # Segundo envío idéntico
    res2 = client.post("/webhooks/woocommerce", content=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "ignored"
    assert data2["reason"] == "duplicate_event"
    assert data2["order_id"] == "ORD-WC-501"


def test_shopify_idempotency(client, sample_payloads):
    """Verifica que el reenvío de un webhook de Shopify no duplique el pedido."""
    payload = sample_payloads["shopify_bytes"]
    headers = sign_shopify(payload, settings.SHOPIFY_WEBHOOK_SECRET)

    res1 = client.post("/webhooks/shopify", content=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    res2 = client.post("/webhooks/shopify", content=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "ignored"
    assert res2.json()["reason"] == "duplicate_event"


def test_stripe_idempotency(client, sample_payloads):
    """Verifica que el reenvío de un evento de Stripe no duplique el pedido."""
    payload = sample_payloads["stripe_bytes"]
    headers = sign_stripe(payload, settings.STRIPE_WEBHOOK_SECRET)

    res1 = client.post("/webhooks/stripe", content=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"
    order_id = res1.json()["order_id"]

    res2 = client.post("/webhooks/stripe", content=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "ignored"
    assert res2.json()["order_id"] == order_id
