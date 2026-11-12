import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app import webhook
from app.main import app

PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "1",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.ROUTETEST1",
                                "timestamp": "1690000000",
                                "text": {"body": "hola"},
                                "type": "text",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(webhook.settings, "WHATSAPP_VERIFY_TOKEN", "my_verify_token")
    monkeypatch.setattr(webhook.settings, "WHATSAPP_APP_SECRET", "my_app_secret")

    async def _noop_handle_and_reply(message):
        return None

    monkeypatch.setattr(webhook, "_handle_and_reply", _noop_handle_and_reply)
    return TestClient(app)


def _sign(body: bytes, secret: str = "my_app_secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_get_webhook_verification_ok(client):
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my_verify_token",
            "hub.challenge": "challenge-accepted-123",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge-accepted-123"


def test_get_webhook_verification_forbidden(client):
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge-accepted-123",
        },
    )
    assert response.status_code == 403


def test_post_webhook_valid_signature_returns_200(client):
    body = json.dumps(PAYLOAD).encode("utf-8")
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200


def test_post_webhook_invalid_signature_returns_401(client):
    body = json.dumps(PAYLOAD).encode("utf-8")
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body, secret="wrong_secret"),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


def test_post_webhook_missing_signature_returns_401(client):
    body = json.dumps(PAYLOAD).encode("utf-8")
    response = client.post("/webhook", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 401
