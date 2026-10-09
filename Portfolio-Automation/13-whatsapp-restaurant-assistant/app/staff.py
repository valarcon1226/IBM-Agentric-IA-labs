"""Staff commands and human-handover notifications (DECISIONES-13 W7).

Only a number listed in `STAFF_WA_IDS` gets staff treatment; anyone else sending `/...` is just a
customer whose message goes to the agent like any other text (checked by `app.conversation`
before this module is even imported for that message). Sending a message to staff/customers here
never raises: like `app.whatsapp`'s callers elsewhere, a failed WhatsApp send is logged and
swallowed so it can never break the conversation pipeline.
"""

import logging
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.database import get_engine
from app.security import mask_wa_id
from app.whatsapp import send_text

logger = logging.getLogger(__name__)

_SELECT_PENDING_ORDERS_TODAY_SQL = text(
    "SELECT id, wa_id, total_cop FROM orders "
    "WHERE status = 'pending' AND created_at::date = CURRENT_DATE ORDER BY created_at"
)


def is_staff(wa_id: str) -> bool:
    return wa_id in settings.staff_wa_id_list


async def _send_or_log(wa_id: str, body: str) -> bool:
    """Send `body` to `wa_id` if WhatsApp is enabled; otherwise just log it (dev mode/tests).
    Returns True on an actual or simulated send, False if sending was attempted and failed."""
    if not settings.WHATSAPP_ENABLED:
        logger.info("WHATSAPP_ENABLED=false, not sending message to %s", mask_wa_id(wa_id))
        return True
    try:
        await send_text(wa_id, body)
    except Exception:
        logger.exception("Failed to send message to %s", mask_wa_id(wa_id))
        return False
    return True


async def notify_staff(reason: str, customer_wa_id: str, summary: str) -> None:
    """Tell every staff number about a handover: reason, masked customer number, short summary."""
    if not settings.staff_wa_id_list:
        return
    body = (
        f"Traspaso a humano.\nCliente: {mask_wa_id(customer_wa_id)}\n"
        f"Motivo: {reason}\nResumen: {summary}"
    )
    for staff_wa_id in settings.staff_wa_id_list:
        await _send_or_log(staff_wa_id, body)


async def _handle_pedidos() -> list[str]:
    async with get_engine().connect() as connection:
        rows = (await connection.execute(_SELECT_PENDING_ORDERS_TODAY_SQL)).all()
    if not rows:
        return ["No hay pedidos pendientes hoy."]
    lines = [
        f"#{order_id} {mask_wa_id(order_wa_id)} - ${total_cop:,} COP".replace(",", ".")
        for order_id, order_wa_id, total_cop in rows
    ]
    return ["Pedidos pendientes de hoy:\n" + "\n".join(lines)]


async def _handle_bot(parts: list[str]) -> list[str]:
    if len(parts) < 2 or not parts[1].strip():
        return ["Uso: /bot <wa_id>"]
    customer_wa_id = parts[1].strip()
    from app.tools import deactivate_handover

    await deactivate_handover(customer_wa_id)
    return [f"El bot vuelve a responder a {mask_wa_id(customer_wa_id)}."]


async def _handle_reply(parts: list[str]) -> list[str]:
    if len(parts) < 3 or not parts[1].strip() or not parts[2].strip():
        return ["Uso: /r <wa_id> <texto>"]
    customer_wa_id = parts[1].strip()
    body = parts[2]
    sent = await _send_or_log(customer_wa_id, body)
    if not sent:
        return ["No se pudo enviar el mensaje al cliente."]
    return [f"Mensaje enviado a {mask_wa_id(customer_wa_id)}."]


async def handle_staff_command(staff_wa_id: str, text_in: str) -> list[str]:
    """Dispatch a `/...` command from a known staff number. Caller must already have checked
    `is_staff(staff_wa_id)`."""
    parts = text_in.strip().split(maxsplit=2)
    command = parts[0].lower()

    handlers: dict[str, Any] = {
        "/pedidos": lambda: _handle_pedidos(),
        "/bot": lambda: _handle_bot(parts),
        "/r": lambda: _handle_reply(parts),
    }
    handler = handlers.get(command)
    if handler is None:
        return [f"Comando no reconocido: {command}. Usa /r, /bot o /pedidos."]
    return await handler()
