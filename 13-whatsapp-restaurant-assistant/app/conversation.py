"""Conversation pipeline shared by the real webhook and `/dev/chat` (DECISIONES-13 W4/W5).

`process_incoming_message` is the single entry point both callers use: it dedupes by WhatsApp
message id, persists every turn in `messages`, enforces the per-customer rate limit, and finally
calls `handle_incoming`, which (W7) first checks whether the sender is staff issuing a `/...`
command, then whether the bot is paused (an active handover) for this customer, before falling
back to the real agent.
"""

from sqlalchemy import text

from app.agent import run_agent
from app.database import get_engine
from app.staff import handle_staff_command, is_staff
from app.tools import is_handover_active

RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_MINUTES = 10

NON_TEXT_REPLY = (
    "Por ahora solo puedo leer mensajes de texto. ¿Podrías escribirme lo que necesitas, por favor?"
)
RATE_LIMIT_REPLY = (
    "Has enviado muchos mensajes en poco tiempo. Por favor espera unos minutos antes de "
    "volver a escribir."
)

_UPSERT_CUSTOMER_SQL = text(
    "INSERT INTO customers (wa_id) VALUES (:wa_id) ON CONFLICT (wa_id) DO NOTHING"
)
_INSERT_MESSAGE_SQL = text(
    "INSERT INTO messages (wa_id, role, content) VALUES (:wa_id, :role, :content)"
)
_MARK_PROCESSED_SQL = text(
    "INSERT INTO processed_messages (message_id) VALUES (:message_id) "
    "ON CONFLICT (message_id) DO NOTHING RETURNING message_id"
)
_COUNT_RECENT_CUSTOMER_MESSAGES_SQL = text(
    "SELECT COUNT(*) FROM messages WHERE wa_id = :wa_id AND role = 'customer' "
    f"AND created_at > NOW() - INTERVAL '{RATE_LIMIT_WINDOW_MINUTES} minutes'"
)


async def mark_processed(message_id: str) -> bool:
    """Record `message_id` as processed. Returns True the first time, False on a retry/duplicate."""
    async with get_engine().begin() as connection:
        result = await connection.execute(_MARK_PROCESSED_SQL, {"message_id": message_id})
        return result.first() is not None


async def record_message(wa_id: str, role: str, content: str) -> None:
    async with get_engine().begin() as connection:
        await connection.execute(_UPSERT_CUSTOMER_SQL, {"wa_id": wa_id})
        await connection.execute(
            _INSERT_MESSAGE_SQL, {"wa_id": wa_id, "role": role, "content": content}
        )


async def check_rate_limit(wa_id: str) -> tuple[bool, bool]:
    """Return (allowed, just_crossed_limit).

    `allowed` is False once a customer has sent more than `RATE_LIMIT_MAX_MESSAGES` messages in
    the trailing window. `just_crossed_limit` is True only the first message past the limit, so
    the caller sends exactly one warning and then stays silent.
    """
    async with get_engine().connect() as connection:
        result = await connection.execute(_COUNT_RECENT_CUSTOMER_MESSAGES_SQL, {"wa_id": wa_id})
        count: int = result.scalar_one()
    if count <= RATE_LIMIT_MAX_MESSAGES:
        return True, False
    return False, count == RATE_LIMIT_MAX_MESSAGES + 1


async def handle_incoming(wa_id: str, text: str) -> list[str]:
    """Single entry point for the conversation logic: staff commands, then the pause check, then
    the real agent (W6/W7)."""
    if is_staff(wa_id) and text.startswith("/"):
        return await handle_staff_command(wa_id, text)
    if await is_handover_active(wa_id):
        return []  # bot stays silent for this customer while a human is handling them
    return await run_agent(wa_id, text)


async def process_incoming_message(
    wa_id: str, message_id: str | None, message_type: str, text: str | None
) -> list[str]:
    """Full pipeline for one inbound message: dedupe, persist, rate-limit, then handle."""
    if message_id is not None:
        is_new = await mark_processed(message_id)
        if not is_new:
            return []

    if message_type != "text" or text is None:
        await record_message(wa_id, "customer", f"[{message_type}]")
        return [NON_TEXT_REPLY]

    await record_message(wa_id, "customer", text)
    allowed, just_crossed = await check_rate_limit(wa_id)
    if not allowed:
        return [RATE_LIMIT_REPLY] if just_crossed else []

    replies = await handle_incoming(wa_id, text)
    for reply in replies:
        await record_message(wa_id, "assistant", reply)
    return replies
