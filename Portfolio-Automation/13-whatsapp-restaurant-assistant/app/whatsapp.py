"""WhatsApp Cloud API client (DECISIONES-13 W4).

`send_text` / `send_template` post against `{GRAPH_API_BASE}/{version}/{phone_number_id}/messages`
with `httpx`. Retries happen only on HTTP 429 or 5xx (never on other errors — those propagate so
the caller can log/handle them). Long text is split under 4096 characters per WhatsApp message.
Phone numbers are always logged masked (`app.security.mask_wa_id`), never the full message body.
"""

import asyncio
import logging

import httpx

from app.config import settings
from app.security import mask_wa_id

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 4096
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 0.5


def split_text(text: str, limit: int = MAX_TEXT_LENGTH) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _messages_url() -> str:
    return (
        f"{settings.GRAPH_API_BASE}/{settings.GRAPH_API_VERSION}"
        f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


def _is_retryable(response: httpx.Response) -> bool:
    return response.status_code == 429 or response.status_code >= 500


async def _post_with_retry(client: httpx.AsyncClient, payload: dict) -> httpx.Response:
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
    response: httpx.Response | None = None
    for attempt in range(_MAX_ATTEMPTS):
        response = await client.post(_messages_url(), json=payload, headers=headers)
        if not _is_retryable(response):
            return response
        if attempt < _MAX_ATTEMPTS - 1:
            await asyncio.sleep(_BASE_BACKOFF_SECONDS * (2**attempt))
    assert response is not None
    return response


async def send_text(
    wa_id: str, text: str, *, client: httpx.AsyncClient | None = None
) -> list[httpx.Response]:
    """Send a text message, splitting it into multiple messages if it exceeds 4096 characters."""
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=10.0)
    responses: list[httpx.Response] = []
    try:
        for chunk in split_text(text):
            logger.info("Sending WhatsApp text to %s (%d chars)", mask_wa_id(wa_id), len(chunk))
            payload = {
                "messaging_product": "whatsapp",
                "to": wa_id,
                "type": "text",
                "text": {"body": chunk},
            }
            responses.append(await _post_with_retry(http_client, payload))
        return responses
    finally:
        if owns_client:
            await http_client.aclose()


async def send_template(
    wa_id: str,
    name: str,
    lang: str,
    params: list[str],
    *,
    client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    """Send an approved template message (required outside the 24h customer-service window)."""
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=10.0)
    try:
        logger.info("Sending WhatsApp template '%s' to %s", name, mask_wa_id(wa_id))
        payload: dict = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "template",
            "template": {
                "name": name,
                "language": {"code": lang},
            },
        }
        if params:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in params],
                }
            ]
        return await _post_with_retry(http_client, payload)
    finally:
        if owns_client:
            await http_client.aclose()
