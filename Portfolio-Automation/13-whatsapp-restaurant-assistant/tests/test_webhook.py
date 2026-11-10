import hashlib
import hmac
import json

from app.webhook import parse_messages, verify_signature, verify_subscription

APP_SECRET = "test_app_secret"

TEXT_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "102290129340398",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550783881",
                            "phone_number_id": "106540352242922",
                        },
                        "contacts": [{"profile": {"name": "Juan Perez"}, "wa_id": "573001234567"}],
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.HBgLNTczMDAxMjM0NTY3FQIAEhggMkY4RUIyQTVCREY4",
                                "timestamp": "1690000000",
                                "text": {"body": "Hola, quiero hacer un pedido"},
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

STATUS_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "102290129340398",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550783881",
                            "phone_number_id": "106540352242922",
                        },
                        "statuses": [
                            {
                                "id": "wamid.STATUSONLY123",
                                "status": "delivered",
                                "timestamp": "1690000001",
                                "recipient_id": "573001234567",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}

IMAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "102290129340398",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550783881",
                            "phone_number_id": "106540352242922",
                        },
                        "contacts": [{"profile": {"name": "Juan Perez"}, "wa_id": "573001234567"}],
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.IMAGE1234567890",
                                "timestamp": "1690000002",
                                "type": "image",
                                "image": {
                                    "mime_type": "image/jpeg",
                                    "sha256": "abc123",
                                    "id": "media-id-123",
                                },
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_valid():
    body = json.dumps(TEXT_PAYLOAD).encode("utf-8")
    assert verify_signature(APP_SECRET, body, _sign(body)) is True


def test_verify_signature_invalid():
    body = json.dumps(TEXT_PAYLOAD).encode("utf-8")
    assert verify_signature(APP_SECRET, body, _sign(body, secret="wrong_secret")) is False


def test_verify_signature_missing_header():
    body = json.dumps(TEXT_PAYLOAD).encode("utf-8")
    assert verify_signature(APP_SECRET, body, None) is False


def test_verify_signature_missing_prefix():
    body = json.dumps(TEXT_PAYLOAD).encode("utf-8")
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(APP_SECRET, body, digest) is False


def test_verify_subscription_ok():
    assert verify_subscription("subscribe", "my_token", "my_token") is True


def test_verify_subscription_wrong_token():
    assert verify_subscription("subscribe", "wrong_token", "my_token") is False


def test_verify_subscription_wrong_mode():
    assert verify_subscription("unsubscribe", "my_token", "my_token") is False


def test_verify_subscription_missing_token():
    assert verify_subscription("subscribe", None, "my_token") is False


def test_parse_messages_extracts_text():
    messages = parse_messages(TEXT_PAYLOAD)
    assert len(messages) == 1
    message = messages[0]
    assert message.wa_id == "573001234567"
    assert message.message_type == "text"
    assert message.text == "Hola, quiero hacer un pedido"
    assert message.message_id.startswith("wamid.")


def test_parse_messages_ignores_statuses():
    assert parse_messages(STATUS_PAYLOAD) == []


def test_parse_messages_extracts_non_text_without_body():
    messages = parse_messages(IMAGE_PAYLOAD)
    assert len(messages) == 1
    message = messages[0]
    assert message.message_type == "image"
    assert message.text is None


def test_parse_messages_empty_payload():
    assert parse_messages({}) == []
