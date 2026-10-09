"""WhatsApp Cloud API webhook (DECISIONES-13 W4): GET verification + POST signature check,
payload parsing, dedupe/rate-limit/send through `app.conversation` and `app.whatsapp`.
"""

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.conversation import process_incoming_message
from app.security import mask_wa_id
from app.whatsapp import send_text

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class IncomingMessage:
    wa_id: str
    message_id: str
    message_type: str
    text: str | None


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    """Verify `X-Hub-Signature-256`: HMAC-SHA256 of the raw body, keyed with the app secret."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def verify_subscription(mode: str | None, token: str | None, verify_token: str) -> bool:
    return mode == "subscribe" and token is not None and secrets.compare_digest(token, verify_token)


def parse_messages(payload: dict[str, Any]) -> list[IncomingMessage]:
    """Extract text/non-text messages from a Meta webhook payload. Status updates are ignored."""
    messages: list[IncomingMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                message_type = message.get("type", "")
                text = message.get("text", {}).get("body") if message_type == "text" else None
                messages.append(
                    IncomingMessage(
                        wa_id=message.get("from", ""),
                        message_id=message.get("id", ""),
                        message_type=message_type,
                        text=text,
                    )
                )
            # `value.get("statuses")` (delivery/read receipts) is intentionally not read: Meta
            # retries those too, but they are not conversation turns.
    return messages


async def _handle_and_reply(message: IncomingMessage) -> None:
    replies = await process_incoming_message(
        message.wa_id, message.message_id, message.message_type, message.text
    )
    if not replies:
        return
    if not settings.WHATSAPP_ENABLED:
        logger.info(
            "WHATSAPP_ENABLED=false, not sending %d repl(y/ies) to %s",
            len(replies),
            mask_wa_id(message.wa_id),
        )
        return
    for reply in replies:
        try:
            await send_text(message.wa_id, reply)
        except Exception:
            logger.exception("Failed to send WhatsApp reply to %s", mask_wa_id(message.wa_id))


@router.get("/webhook")
async def verify_webhook(request: Request) -> PlainTextResponse:
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge", "")
    if settings.WHATSAPP_VERIFY_TOKEN and verify_subscription(
        mode, token, settings.WHATSAPP_VERIFY_TOKEN
    ):
        return PlainTextResponse(challenge, status_code=200)
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    app_secret = settings.WHATSAPP_APP_SECRET or ""
    if not app_secret or not verify_signature(app_secret, body, signature_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    for message in parse_messages(payload):
        background_tasks.add_task(_handle_and_reply, message)
    return {"status": "received"}
