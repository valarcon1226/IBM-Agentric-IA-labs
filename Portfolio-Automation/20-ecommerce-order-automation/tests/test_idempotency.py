"""Pruebas de idempotencia en la ingesta de webhooks para evitar duplicación de pedidos."""

import asyncio
import json

import httpx
import pytest
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database import InMemoryRepository, get_repository
from app.main import app
from app.models import OrderSource, WebhookEvent
from app.normalizers import normalize_woocommerce_order
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


def test_concurrent_deliveries_race_condition(sample_payloads, monkeypatch):
    """Verifica que N entregas simultáneas del mismo pedido respondan 200,

    guarden exactamente un pedido y envíen notificaciones una sola vez.
    """
    notifications_sent = []

    def spy_notify_dispatch(order):
        notifications_sent.append(order.id)
        return True

    def spy_notify_whatsapp(order, status, note=""):
        return True

    monkeypatch.setattr("app.routes.webhooks.notify_order_ready_for_dispatch", spy_notify_dispatch)
    monkeypatch.setattr("app.routes.webhooks.notify_whatsapp_order_status", spy_notify_whatsapp)

    async def _run():
        payload = sample_payloads["wc_bytes"]
        headers = sign_woocommerce(payload, settings.WOOCOMMERCE_WEBHOOK_SECRET)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as async_client:
            tasks = [
                async_client.post(
                    "/webhooks/woocommerce",
                    content=payload,
                    headers={**headers, "x-wc-webhook-id": f"concurrent-race-{i}"},
                )
                for i in range(10)
            ]
            responses = await asyncio.gather(*tasks)

        # 1. Todas responden HTTP 200
        for r in responses:
            assert r.status_code == 200

        data_list = [r.json() for r in responses]
        processed = [d for d in data_list if d.get("status") == "processed"]
        ignored = [d for d in data_list if d.get("status") == "ignored"]

        assert len(processed) == 1
        assert len(ignored) == 9
        for d in ignored:
            assert d.get("reason") == "duplicate_event"
            assert d.get("order_id") == "ORD-WC-501"

        # 2. Exactamente un pedido guardado en el repositorio
        repo = get_repository()
        orders = await repo.list_orders()
        assert len(orders) == 1
        assert orders[0].id == "ORD-WC-501"

        # 3. Notificación enviada una sola vez
        assert len(notifications_sent) == 1

    asyncio.run(_run())


def test_in_memory_repository_rejects_duplicates(sample_payloads):
    """Verifica directamente que InMemoryRepository rechaza duplicados de pedidos y eventos."""
    async def _run():
        repo = InMemoryRepository()

        # Probar que create_order rechaza duplicados
        order = normalize_woocommerce_order(json.loads(sample_payloads["wc_bytes"].decode("utf-8")))
        await repo.create_order(order)
        assert await repo.get_order(order.id) is not None

        with pytest.raises(DuplicateKeyError):
            await repo.create_order(order)

        # Probar que create_event rechaza duplicados
        event = WebhookEvent(
            event_id="evt_test_dup",
            source=OrderSource.WOOCOMMERCE,
            event_type="order.created",
            payload_hash="sample_hash_123",
        )
        await repo.create_event(event)
        with pytest.raises(DuplicateKeyError):
            await repo.create_event(event)

    asyncio.run(_run())
