"""Normalizadores para convertir payloads dispares de WooCommerce, Shopify y Stripe

a un modelo de datos unificado de Orden de Café de Origen.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.models import (
    Customer,
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    PaymentStatus,
    ShippingAddress,
    StatusHistoryEntry,
)

logger = logging.getLogger("cafe_de_origen.normalizers")


def normalize_woocommerce_order(payload: Dict[str, Any]) -> Order:
    """Normaliza un pedido proveniente del webhook de WooCommerce."""
    ext_id = str(payload.get("id") or payload.get("number") or "wc_unknown")
    order_number = payload.get("number", ext_id)
    raw_status = str(payload.get("status", "")).lower()

    # Mapeo de estado y pago
    if raw_status in ("processing", "completed"):
        payment_status = PaymentStatus.PAID
        order_status = OrderStatus.LISTO_PARA_DESPACHAR
    elif raw_status in ("cancelled", "refunded", "failed"):
        payment_status = PaymentStatus.FAILED
        order_status = OrderStatus.CANCELADO
    else:
        payment_status = PaymentStatus.PENDING
        order_status = OrderStatus.PENDIENTE

    # Cliente y dirección
    billing = payload.get("billing") or {}
    shipping = payload.get("shipping") or {}

    first_name = billing.get("first_name") or shipping.get("first_name", "")
    last_name = billing.get("last_name") or shipping.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or "Cliente WooCommerce"

    customer = Customer(
        name=full_name,
        email=billing.get("email") or "cliente@cafedeorigen.co",
        phone=billing.get("phone") or "",
        shipping_address=ShippingAddress(
            street=shipping.get("address_1") or billing.get("address_1", ""),
            city=shipping.get("city") or billing.get("city", "Bogotá"),
            state=shipping.get("state") or billing.get("state", "Cundinamarca"),
            postal_code=shipping.get("postcode") or billing.get("postcode", ""),
            country=shipping.get("country") or billing.get("country", "CO"),
        ),
    )

    # Líneas de pedido
    items = []
    for item in payload.get("line_items", []):
        qty = int(item.get("quantity", 1))
        unit_price = float(item.get("price") or (float(item.get("total", 0)) / max(qty, 1)))
        total_price = float(item.get("total") or (unit_price * qty))
        items.append(
            OrderItem(
                sku=str(item.get("sku") or f"SKU-{item.get('id', 'item')}"),
                title=str(item.get("name") or "Café de Especialidad"),
                quantity=qty,
                unit_price=unit_price,
                total_price=total_price,
            )
        )

    total_amount = float(payload.get("total", 0.0))
    currency = str(payload.get("currency", "COP")).upper()
    now = datetime.now(timezone.utc)

    order_id = f"ORD-WC-{order_number}"
    return Order(
        id=order_id,
        external_id=ext_id,
        source=OrderSource.WOOCOMMERCE,
        status=order_status,
        payment_status=payment_status,
        customer=customer,
        items=items,
        total_amount=total_amount,
        currency=currency,
        created_at=now,
        updated_at=now,
        history=[
            StatusHistoryEntry(
                from_status="nuevo",
                to_status=order_status.value,
                timestamp=now,
                note="Pedido recibido y normalizado desde WooCommerce webhook",
            )
        ],
        metadata={"raw_status": raw_status, "payment_method": payload.get("payment_method_title")},
    )


def normalize_shopify_order(payload: Dict[str, Any]) -> Order:
    """Normaliza un pedido proveniente del webhook de Shopify (orders/create)."""
    ext_id = str(payload.get("id") or "shopify_unknown")
    order_name = payload.get("name", f"#{ext_id}").replace("#", "")
    fin_status = str(payload.get("financial_status", "")).lower()

    if fin_status == "paid":
        payment_status = PaymentStatus.PAID
        order_status = OrderStatus.LISTO_PARA_DESPACHAR
    elif fin_status in ("voided", "refunded"):
        payment_status = PaymentStatus.FAILED
        order_status = OrderStatus.CANCELADO
    else:
        payment_status = PaymentStatus.PENDING
        order_status = OrderStatus.PENDIENTE

    # Cliente y envío
    customer_data = payload.get("customer") or {}
    shipping_data = payload.get("shipping_address") or payload.get("billing_address") or {}

    c_first = customer_data.get("first_name") or shipping_data.get("first_name", "")
    c_last = customer_data.get("last_name") or shipping_data.get("last_name", "")
    full_name = f"{c_first} {c_last}".strip() or "Cliente Shopify"

    customer = Customer(
        name=full_name,
        email=payload.get("email") or customer_data.get("email") or "cliente@cafedeorigen.co",
        phone=payload.get("phone") or customer_data.get("phone") or shipping_data.get("phone", ""),
        shipping_address=ShippingAddress(
            street=shipping_data.get("address1", ""),
            city=shipping_data.get("city", "Medellín"),
            state=shipping_data.get("province", "Antioquia"),
            postal_code=shipping_data.get("zip", ""),
            country=shipping_data.get("country_code", "CO"),
        ),
    )

    items = []
    for item in payload.get("line_items", []):
        qty = int(item.get("quantity", 1))
        unit_price = float(item.get("price", 0.0))
        items.append(
            OrderItem(
                sku=str(item.get("sku") or f"SKU-{item.get('id', 'item')}"),
                title=str(item.get("title") or item.get("name") or "Café Colombiano"),
                quantity=qty,
                unit_price=unit_price,
                total_price=unit_price * qty,
            )
        )

    total_amount = float(payload.get("total_price", 0.0))
    currency = str(payload.get("currency", "COP")).upper()
    now = datetime.now(timezone.utc)

    order_id = f"ORD-SHP-{order_name}"
    return Order(
        id=order_id,
        external_id=ext_id,
        source=OrderSource.SHOPIFY,
        status=order_status,
        payment_status=payment_status,
        customer=customer,
        items=items,
        total_amount=total_amount,
        currency=currency,
        created_at=now,
        updated_at=now,
        history=[
            StatusHistoryEntry(
                from_status="nuevo",
                to_status=order_status.value,
                timestamp=now,
                note=f"Pedido recibido y normalizado desde Shopify ({fin_status})",
            )
        ],
        metadata={
            "financial_status": fin_status,
            "fulfillment_status": payload.get("fulfillment_status"),
        },
    )


def normalize_stripe_payment_intent(event: Dict[str, Any]) -> Order:
    """Normaliza un evento payment_intent.succeeded de Stripe."""
    obj = event.get("data", {}).get("object", {}) if "data" in event else event
    pi_id = str(obj.get("id") or "pi_unknown")
    metadata = obj.get("metadata") or {}

    raw_amount = float(obj.get("amount", 0))
    currency = str(obj.get("currency", "cop")).upper()

    # Stripe entrega montos en centavos para divisas con decimales
    total_amount = raw_amount / 100.0 if raw_amount >= 100 else raw_amount

    # Extraer información del cliente desde metadata o shipping
    shipping = obj.get("shipping") or {}
    shipping_addr = shipping.get("address") or {}

    customer_name = (
        metadata.get("customer_name")
        or shipping.get("name")
        or obj.get("customer_name")
        or "Cliente Stripe"
    )
    customer_email = (
        metadata.get("customer_email") or obj.get("receipt_email") or "cliente@cafedeorigen.co"
    )
    customer_phone = metadata.get("customer_phone") or shipping.get("phone") or ""

    customer = Customer(
        name=customer_name,
        email=customer_email,
        phone=customer_phone,
        shipping_address=ShippingAddress(
            street=metadata.get("shipping_street") or shipping_addr.get("line1", ""),
            city=metadata.get("shipping_city") or shipping_addr.get("city", "Bogotá"),
            state=metadata.get("shipping_state") or shipping_addr.get("state", "Cundinamarca"),
            postal_code=metadata.get("shipping_postal_code")
            or shipping_addr.get("postal_code", ""),
            country=shipping_addr.get("country", "CO"),
        ),
    )

    # Reconstruir items desde metadata si vienen empaquetados en JSON
    items = []
    items_raw = metadata.get("items")
    if items_raw:
        try:
            parsed_items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
            for it in parsed_items:
                qty = int(it.get("quantity", 1))
                u_price = float(it.get("unit_price", 0.0))
                items.append(
                    OrderItem(
                        sku=str(it.get("sku", "CF-GEN-250")),
                        title=str(it.get("title", "Café de Especialidad")),
                        quantity=qty,
                        unit_price=u_price,
                        total_price=float(it.get("total_price", u_price * qty)),
                    )
                )
        except Exception as e:
            logger.warning("No se pudo parsear metadata de items de Stripe: %s", e)

    if not items:
        # Ítem sintético para representar el pago
        items.append(
            OrderItem(
                sku="CF-STRIPE-PAY",
                title=metadata.get("product_title", "Pedido Café de Origen"),
                quantity=1,
                unit_price=total_amount,
                total_price=total_amount,
            )
        )

    now = datetime.now(timezone.utc)
    short_pi = pi_id[-6:] if len(pi_id) >= 6 else pi_id
    order_id = f"ORD-STP-{short_pi.upper()}"

    return Order(
        id=order_id,
        external_id=pi_id,
        source=OrderSource.STRIPE,
        status=OrderStatus.LISTO_PARA_DESPACHAR,
        payment_status=PaymentStatus.PAID,
        customer=customer,
        items=items,
        total_amount=total_amount,
        currency=currency,
        created_at=now,
        updated_at=now,
        history=[
            StatusHistoryEntry(
                from_status="nuevo",
                to_status=OrderStatus.LISTO_PARA_DESPACHAR.value,
                timestamp=now,
                note=f"Pago confirmado por Stripe ({pi_id})",
            )
        ],
        metadata={
            "payment_intent_id": pi_id,
            "status": obj.get("status"),
            "payment_method_types": obj.get("payment_method_types", []),
        },
    )
