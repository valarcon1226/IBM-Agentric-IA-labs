"""Endpoints para la recepción, verificación de firma e ingesta idempotente de Webhooks."""

import hashlib
import json
import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import settings
from app.database import get_repository
from app.models import OrderSource, OrderStatus, WebhookEvent
from app.normalizers import (
    normalize_shopify_order,
    normalize_stripe_payment_intent,
    normalize_woocommerce_order,
)
from app.notifications import (
    notify_order_ready_for_dispatch,
    notify_whatsapp_order_status,
)
from app.security import (
    verify_shopify_signature,
    verify_stripe_signature,
    verify_woocommerce_signature,
)

logger = logging.getLogger("cafe_de_origen.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ==========================================================
# 1. WOOCOMMERCE WEBHOOK (order.created)
# ==========================================================
@router.post("/woocommerce", summary="Webhook de WooCommerce (order.created)")
async def receive_woocommerce_webhook(
    request: Request,
    x_wc_webhook_signature: str = Header(None, alias="x-wc-webhook-signature"),
    x_wc_webhook_id: str = Header(None, alias="x-wc-webhook-id"),
    x_wc_webhook_topic: str = Header(None, alias="x-wc-webhook-topic"),
):
    """Recibe evento de WooCommerce, valida firma HMAC-SHA256 y procesa el pedido."""
    raw_body = await request.body()

    # 1. Verificación criptográfica de firma
    if not verify_woocommerce_signature(
        raw_body, x_wc_webhook_signature, settings.WOOCOMMERCE_WEBHOOK_SECRET
    ):
        logger.warning("Intento de webhook WooCommerce con firma inválida o ausente.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de webhook WooCommerce inválida (x-wc-webhook-signature).",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"JSON inválido: {e}") from e

    # 2. Idempotencia
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    wc_order_id = str(payload.get("id", "unknown"))
    event_id = x_wc_webhook_id or f"wc_{wc_order_id}_{payload.get('date_modified', '')}"

    repo = get_repository()
    existing_event = await repo.get_event(event_id, payload_hash)
    if existing_event and existing_event.processed:
        logger.info("Evento WooCommerce duplicado detectado (id: %s). Ignorando.", event_id)
        return {
            "status": "ignored",
            "reason": "duplicate_event",
            "order_id": existing_event.order_id,
            "event_id": event_id,
        }

    # Registrar evento
    event_record = WebhookEvent(
        event_id=event_id,
        source=OrderSource.WOOCOMMERCE,
        event_type=x_wc_webhook_topic or "order.created",
        payload_hash=payload_hash,
    )
    await repo.create_event(event_record)

    # 3. Normalización del pedido
    order = normalize_woocommerce_order(payload)
    await repo.create_order(order)

    # 4. Notificaciones si el pedido está listo para despacho
    if order.status == OrderStatus.LISTO_PARA_DESPACHAR:
        notify_order_ready_for_dispatch(order)
        notify_whatsapp_order_status(order, "listo_para_despachar")

    await repo.mark_event_processed(event_id, order.id)
    return {
        "status": "processed",
        "order_id": order.id,
        "external_id": order.external_id,
        "order_status": order.status.value,
        "total": order.total_amount,
    }


# ==========================================================
# 2. SHOPIFY WEBHOOK (orders/create)
# ==========================================================
@router.post("/shopify", summary="Webhook de Shopify (orders/create)")
async def receive_shopify_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None, alias="x-shopify-hmac-sha256"),
    x_shopify_webhook_id: str = Header(None, alias="x-shopify-webhook-id"),
    x_shopify_topic: str = Header(None, alias="x-shopify-topic"),
):
    """Recibe evento de Shopify, valida firma HMAC-SHA256 y normaliza el pedido."""
    raw_body = await request.body()

    # 1. Verificación de firma
    if not verify_shopify_signature(
        raw_body, x_shopify_hmac_sha256, settings.SHOPIFY_WEBHOOK_SECRET
    ):
        logger.warning("Intento de webhook Shopify con firma inválida o ausente.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de webhook Shopify inválida (x-shopify-hmac-sha256).",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"JSON inválido: {e}") from e

    # 2. Idempotencia
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    shopify_id = str(payload.get("id", "unknown"))
    event_id = x_shopify_webhook_id or f"shopify_{shopify_id}"

    repo = get_repository()
    existing_event = await repo.get_event(event_id, payload_hash)
    if existing_event and existing_event.processed:
        logger.info("Evento Shopify duplicado detectado (id: %s). Ignorando.", event_id)
        return {
            "status": "ignored",
            "reason": "duplicate_event",
            "order_id": existing_event.order_id,
            "event_id": event_id,
        }

    event_record = WebhookEvent(
        event_id=event_id,
        source=OrderSource.SHOPIFY,
        event_type=x_shopify_topic or "orders/create",
        payload_hash=payload_hash,
    )
    await repo.create_event(event_record)

    # 3. Normalización
    order = normalize_shopify_order(payload)
    await repo.create_order(order)

    # 4. Notificaciones
    if order.status == OrderStatus.LISTO_PARA_DESPACHAR:
        notify_order_ready_for_dispatch(order)
        notify_whatsapp_order_status(order, "listo_para_despachar")

    await repo.mark_event_processed(event_id, order.id)
    return {
        "status": "processed",
        "order_id": order.id,
        "external_id": order.external_id,
        "order_status": order.status.value,
        "total": order.total_amount,
    }


# ==========================================================
# 3. STRIPE WEBHOOK (payment_intent.succeeded)
# ==========================================================
@router.post("/stripe", summary="Webhook de Stripe (payment_intent.succeeded)")
async def receive_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """Recibe evento de Stripe usando la librería oficial y tolerancia de tiempo."""
    raw_body = await request.body()

    # 1. Verificación oficial de firma y tolerancia temporal (300s)
    try:
        stripe_event = verify_stripe_signature(
            raw_body=raw_body,
            signature_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
            tolerance_seconds=300,
        )
    except stripe.error.SignatureVerificationError as err:
        logger.warning("Firma de Stripe rechazada: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Firma de Stripe inválida o fuera de tolerancia: {err}",
        ) from err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error procesando payload de Stripe: {e}",
        ) from e

    # 2. Idempotencia
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    event_id = stripe_event.get("id") or f"stripe_{payload_hash[:16]}"
    event_type = stripe_event.get("type", "unknown")

    repo = get_repository()
    existing_event = await repo.get_event(event_id, payload_hash)
    if existing_event and existing_event.processed:
        logger.info("Evento Stripe duplicado detectado (id: %s). Ignorando.", event_id)
        return {
            "status": "ignored",
            "reason": "duplicate_event",
            "order_id": existing_event.order_id,
            "event_id": event_id,
        }

    event_record = WebhookEvent(
        event_id=event_id,
        source=OrderSource.STRIPE,
        event_type=event_type,
        payload_hash=payload_hash,
    )
    await repo.create_event(event_record)

    # 3. Normalización y despacho si el pago fue exitoso
    if event_type in ("payment_intent.succeeded", "checkout.session.completed"):
        order = normalize_stripe_payment_intent(stripe_event)
        await repo.create_order(order)

        if order.status == OrderStatus.LISTO_PARA_DESPACHAR:
            notify_order_ready_for_dispatch(order)
            notify_whatsapp_order_status(order, "listo_para_despachar")

        await repo.mark_event_processed(event_id, order.id)
        return {
            "status": "processed",
            "order_id": order.id,
            "external_id": order.external_id,
            "order_status": order.status.value,
            "total": order.total_amount,
        }

    # Si es otro tipo de evento reconocido por Stripe
    await repo.mark_event_processed(
        event_id, "n/a", {"note": f"Evento {event_type} recibido pero no requiere pedido"}
    )
    return {"status": "received", "event_id": event_id, "type": event_type}
