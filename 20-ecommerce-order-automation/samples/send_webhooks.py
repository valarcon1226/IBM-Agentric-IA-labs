"""Script de demostración para firmar y enviar webhooks de WooCommerce, Shopify y Stripe.

Permite simular el flujo completo de compras sin requerir cuentas reales en producción.
"""

import argparse
import base64
import hashlib
import hmac
import os
import sys
import time
from typing import Dict

import httpx

# Secretos por defecto sincronizados con .env.example
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_WC_SECRET = "change_me_woocommerce_secret"
DEFAULT_SHOPIFY_SECRET = "change_me_shopify_secret"
DEFAULT_STRIPE_SECRET = "whsec_change_me_stripe_secret"

SAMPLES_DIR = os.path.dirname(__file__)


def sign_woocommerce(payload_bytes: bytes, secret: str) -> Dict[str, str]:
    """Genera encabezados válidos para el webhook de WooCommerce."""
    sig = base64.b64encode(
        hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    ).decode("ascii")
    return {
        "Content-Type": "application/json",
        "x-wc-webhook-signature": sig,
        "x-wc-webhook-topic": "order.created",
        "x-wc-webhook-id": "wc_delivery_sample_501",
    }


def sign_shopify(payload_bytes: bytes, secret: str) -> Dict[str, str]:
    """Genera encabezados válidos para el webhook de Shopify."""
    sig = base64.b64encode(
        hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    ).decode("ascii")
    return {
        "Content-Type": "application/json",
        "X-Shopify-Hmac-Sha256": sig,
        "X-Shopify-Topic": "orders/create",
        "X-Shopify-Webhook-Id": "shopify_webhook_1042",
    }


def sign_stripe(payload_bytes: bytes, secret: str) -> Dict[str, str]:
    """Genera encabezado Stripe-Signature con timestamp actual y HMAC-SHA256 v1."""
    timestamp = int(time.time())
    payload_str = payload_bytes.decode("utf-8")
    signed_payload = f"{timestamp}.{payload_str}"
    v1_sig = hmac.new(
        secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    sig_header = f"t={timestamp},v1={v1_sig}"
    return {
        "Content-Type": "application/json",
        "Stripe-Signature": sig_header,
    }


def run_demo(base_url: str = DEFAULT_BASE_URL) -> None:
    """Ejecuta la secuencia completa de demostración con los 3 canales + pruebas de seguridad."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 70)
    print("DEMO: ENVIO Y VALIDACION DE WEBHOOKS - CAFE DE ORIGEN")
    print(f"Destino: {base_url}")
    print("=" * 70)

    wc_path = os.path.join(SAMPLES_DIR, "woocommerce_order_created.json")
    shopify_path = os.path.join(SAMPLES_DIR, "shopify_orders_create.json")
    stripe_path = os.path.join(SAMPLES_DIR, "stripe_payment_intent_succeeded.json")

    with open(wc_path, "rb") as f:
        wc_bytes = f.read()

    with open(shopify_path, "rb") as f:
        shopify_bytes = f.read()

    with open(stripe_path, "rb") as f:
        stripe_bytes = f.read()

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        # 1. Enviar WooCommerce
        print("\n[1/5] [WooCommerce] Enviando pedido WooCommerce (order.created)...")
        wc_headers = sign_woocommerce(wc_bytes, DEFAULT_WC_SECRET)
        res_wc = client.post("/webhooks/woocommerce", content=wc_bytes, headers=wc_headers)
        print(f"  Status: {res_wc.status_code}")
        print(f"  Respuesta: {res_wc.json()}")

        # 2. Enviar Shopify
        print("\n[2/5] [Shopify] Enviando pedido Shopify (orders/create)...")
        shp_headers = sign_shopify(shopify_bytes, DEFAULT_SHOPIFY_SECRET)
        res_shp = client.post("/webhooks/shopify", content=shopify_bytes, headers=shp_headers)
        print(f"  Status: {res_shp.status_code}")
        print(f"  Respuesta: {res_shp.json()}")

        # 3. Enviar Stripe
        print("\n[3/5] [Stripe] Enviando pago Stripe (payment_intent.succeeded)...")
        stp_headers = sign_stripe(stripe_bytes, DEFAULT_STRIPE_SECRET)
        res_stp = client.post("/webhooks/stripe", content=stripe_bytes, headers=stp_headers)
        print(f"  Status: {res_stp.status_code}")
        print(f"  Respuesta: {res_stp.json()}")

        # 4. Probar Idempotencia (Reenvío de WooCommerce)
        print("\n[4/5] [Idempotencia] Probando reenvio del mismo pedido WooCommerce...")
        res_dup = client.post("/webhooks/woocommerce", content=wc_bytes, headers=wc_headers)
        print(f"  Status: {res_dup.status_code}")
        print(f"  Respuesta: {res_dup.json()}")
        if res_dup.json().get("status") == "ignored":
            print("  [OK] EXITO: El evento duplicado fue ignorado sin crear pedido repetido.")

        # 5. Probar Rechazo de Firma Inválida
        print("\n[5/5] [Seguridad] Probando rechazo de firma invalida o alterada...")
        bad_headers = {
            "Content-Type": "application/json",
            "x-wc-webhook-signature": "firma_falsa_o_alterada_abc123==",
        }
        res_bad = client.post("/webhooks/woocommerce", content=wc_bytes, headers=bad_headers)
        print(f"  Status: {res_bad.status_code} (Esperado 401)")
        print(f"  Respuesta: {res_bad.json()}")
        if res_bad.status_code == 401:
            print("  [OK] EXITO: Peticion rechazada con 401 Unauthorized.")

    print("\n" + "=" * 70)
    print("Demostracion completada exitosamente.")
    print("Accede a http://localhost:8000/admin para revisar los pedidos en el panel.")
    print("Accede a http://localhost:8025 para revisar los correos en Mailpit.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envía webhooks simulados a Café de Origen API")
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help="URL base del servicio (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    try:
        run_demo(args.url)
    except Exception as exc:
        print(f"\n❌ Error ejecutando el script de webhooks: {exc}", file=sys.stderr)
        sys.exit(1)
