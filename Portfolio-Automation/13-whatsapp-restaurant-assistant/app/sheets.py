"""Google Sheets sync (DECISIONES-13 W8), optional: active only when both
`GOOGLE_SERVICE_ACCOUNT_JSON` and `GOOGLE_SHEET_ID` are configured. Appends one row per order,
reservation and event lead to its own tab. A failure here (bad credentials, Sheets unreachable,
rate limit) is logged and swallowed — it must never break the conversation, same contract as
`app.whatsapp`.

Uses `google-auth` only to turn the service account JSON into a bearer token (the token exchange
is a blocking call, run in a thread via `asyncio.to_thread`); the actual `values:append` call goes
through `httpx`, like every other outbound HTTP call in this project.
"""

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

ORDERS_TAB = "Pedidos"
RESERVATIONS_TAB = "Reservas"
EVENT_LEADS_TAB = "Eventos"


def _enabled() -> bool:
    return bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON and settings.GOOGLE_SHEET_ID)


def _access_token() -> str:
    # Imported lazily: google-auth is an optional dependency path, and importing it at module
    # load time would fail hard for every deployment that never configures Sheets.
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON or "{}")
    credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    credentials.refresh(Request())
    return credentials.token


async def _append_row(tab: str, row: list[Any]) -> None:
    if not _enabled():
        return
    try:
        token = await asyncio.to_thread(_access_token)
        url = (
            f"{_SHEETS_API_BASE}/{settings.GOOGLE_SHEET_ID}/values/{tab}!A1:append"
            "?valueInputOption=USER_ENTERED"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"values": [row]},
            )
            response.raise_for_status()
    except Exception:
        logger.exception("Failed to append a row to Google Sheets tab '%s'", tab)


async def append_order(order: dict[str, Any], wa_id: str) -> None:
    await _append_row(
        ORDERS_TAB,
        [
            order.get("order_id"),
            wa_id,
            order.get("subtotal_cop"),
            order.get("delivery_fee_cop"),
            order.get("total_cop"),
            order.get("status"),
        ],
    )


async def append_reservation(reservation: dict[str, Any], wa_id: str) -> None:
    await _append_row(
        RESERVATIONS_TAB,
        [
            reservation.get("reservation_id"),
            wa_id,
            reservation.get("date"),
            reservation.get("time"),
            reservation.get("party_size"),
            reservation.get("status"),
        ],
    )


async def append_event_lead(lead: dict[str, Any], wa_id: str, arguments: dict[str, Any]) -> None:
    await _append_row(
        EVENT_LEADS_TAB,
        [
            lead.get("lead_id"),
            wa_id,
            arguments.get("event_type"),
            arguments.get("date"),
            arguments.get("guests"),
            arguments.get("budget"),
            arguments.get("contact_name"),
        ],
    )
