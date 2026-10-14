"""Pruebas de verificación criptográfica de firmas de webhooks (WooCommerce, Shopify y Stripe)."""

import hashlib
import hmac
import time

from app.config import settings
from samples.send_webhooks import sign_shopify, sign_stripe, sign_woocommerce


def test_woocommerce_webhook_valid_signature(client, sample_payloads):
    """Verifica que un webhook de WooCommerce con firma válida se acepte y procese."""
    payload = sample_payloads["wc_bytes"]
    headers = sign_woocommerce(payload, settings.WOOCOMMERCE_WEBHOOK_SECRET)

    response = client.post("/webhooks/woocommerce", content=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["order_id"] == "ORD-WC-501"
    assert data["order_status"] == "listo_para_despachar"


def test_woocommerce_webhook_invalid_signature(client, sample_payloads):
    """Verifica que una firma alterada de WooCommerce sea rechazada con 401."""
    payload = sample_payloads["wc_bytes"]
    headers = {
        "Content-Type": "application/json",
        "x-wc-webhook-signature": "firma_invalida_totalmente_falsa==",
    }

    response = client.post("/webhooks/woocommerce", content=payload, headers=headers)
    assert response.status_code == 401
    assert "inválida" in response.json()["detail"].lower()


def test_woocommerce_webhook_missing_signature(client, sample_payloads):
    """Verifica que un webhook sin encabezado de firma sea rechazado con 401."""
    payload = sample_payloads["wc_bytes"]
    response = client.post("/webhooks/woocommerce", content=payload)
    assert response.status_code == 401


def test_shopify_webhook_valid_signature(client, sample_payloads):
    """Verifica que un webhook de Shopify con firma válida HMAC-SHA256 se acepte."""
    payload = sample_payloads["shopify_bytes"]
    headers = sign_shopify(payload, settings.SHOPIFY_WEBHOOK_SECRET)

    response = client.post("/webhooks/shopify", content=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["order_id"] == "ORD-SHP-1042"
    assert data["order_status"] == "listo_para_despachar"


def test_shopify_webhook_invalid_signature(client, sample_payloads):
    """Verifica que una firma alterada de Shopify sea rechazada con 401."""
    payload = sample_payloads["shopify_bytes"]
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Hmac-Sha256": "firma_falsa_shopify==",
    }

    response = client.post("/webhooks/shopify", content=payload, headers=headers)
    assert response.status_code == 401
    assert "inválida" in response.json()["detail"].lower()


def test_stripe_webhook_valid_signature(client, sample_payloads):
    """Verifica que un evento payment_intent.succeeded con firma Stripe válida se procese."""
    payload = sample_payloads["stripe_bytes"]
    headers = sign_stripe(payload, settings.STRIPE_WEBHOOK_SECRET)

    response = client.post("/webhooks/stripe", content=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert "ORD-STP-" in data["order_id"]
    assert data["order_status"] == "listo_para_despachar"


def test_stripe_webhook_invalid_signature(client, sample_payloads):
    """Verifica que una firma Stripe con clave o hash erróneo sea rechazada con 400."""
    payload = sample_payloads["stripe_bytes"]
    headers = {
        "Content-Type": "application/json",
        "Stripe-Signature": "t=1700000000,v1=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    }

    response = client.post("/webhooks/stripe", content=payload, headers=headers)
    assert response.status_code == 400
    assert "inválida" in response.json()["detail"].lower()


def test_stripe_webhook_expired_signature(client, sample_payloads):
    """Verifica que un webhook de Stripe con timestamp vencido (>300s de tolerancia) sea rechazado."""
    payload = sample_payloads["stripe_bytes"]
    secret = settings.STRIPE_WEBHOOK_SECRET

    # Timestamp de hace 600 segundos (10 minutos, superior a la tolerancia de 300s)
    expired_timestamp = int(time.time()) - 600
    signed_payload = f"{expired_timestamp}.{payload.decode('utf-8')}"
    v1_sig = hmac.new(
        secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Stripe-Signature": f"t={expired_timestamp},v1={v1_sig}",
    }

    response = client.post("/webhooks/stripe", content=payload, headers=headers)
    assert response.status_code == 400
    assert (
        "tolerancia" in response.json()["detail"].lower()
        or "timestamp" in response.json()["detail"].lower()
    )
