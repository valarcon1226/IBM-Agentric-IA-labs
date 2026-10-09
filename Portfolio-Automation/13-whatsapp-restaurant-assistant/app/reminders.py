"""Day-before reservation reminders (DECISIONES-13 W9): a periodic task started from the API
lifespan, running every `REMINDER_INTERVAL_SECONDS` in the same single process (no Celery/Redis,
per DECISIONES-13 W12).

For every confirmed reservation for tomorrow with `reminder_sent_at IS NULL`, sends
`REMINDER_TEMPLATE` (outside WhatsApp's 24h customer-service window an approved template is
required) and marks it sent — exactly once per reservation. If `WHATSAPP_ENABLED=false` (dev
mode), the send is only logged, same convention as `app.webhook`/`app.staff`, and the reminder is
still marked sent so dev-mode runs don't retry forever. A real send failure is logged and *not*
marked sent, so it is retried on the next tick.
"""

import asyncio
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.config import settings
from app.database import get_engine
from app.security import mask_wa_id
from app.whatsapp import send_template

logger = logging.getLogger(__name__)

BOGOTA_TZ = ZoneInfo("America/Bogota")
REMINDER_INTERVAL_SECONDS = 10 * 60

_SELECT_DUE_REMINDERS_SQL = text(
    "SELECT id, wa_id, reservation_date, reservation_time, party_size FROM reservations "
    "WHERE reservation_date = :tomorrow AND status = 'confirmed' AND reminder_sent_at IS NULL"
)
_MARK_REMINDER_SENT_SQL = text(
    "UPDATE reservations SET reminder_sent_at = :sent_at WHERE id = :reservation_id"
)


async def _mark_sent(reservation_id: int) -> None:
    async with get_engine().begin() as connection:
        await connection.execute(
            _MARK_REMINDER_SENT_SQL,
            {
                "reservation_id": reservation_id,
                "sent_at": dt.datetime.now(BOGOTA_TZ).replace(tzinfo=None),
            },
        )


async def send_due_reminders() -> int:
    """Send (and mark) the reminder for every reservation due tomorrow. Returns how many were
    sent/marked this tick."""
    tomorrow = dt.datetime.now(BOGOTA_TZ).date() + dt.timedelta(days=1)
    async with get_engine().connect() as connection:
        rows = (await connection.execute(_SELECT_DUE_REMINDERS_SQL, {"tomorrow": tomorrow})).all()

    sent = 0
    for reservation_id, wa_id, reservation_date, reservation_time, party_size in rows:
        params = [
            reservation_date.isoformat(),
            reservation_time.isoformat(timespec="minutes"),
            str(party_size),
        ]
        if settings.WHATSAPP_ENABLED:
            try:
                await send_template(wa_id, settings.REMINDER_TEMPLATE, "es", params)
            except Exception:
                logger.exception(
                    "Failed to send reservation reminder to %s; will retry next tick",
                    mask_wa_id(wa_id),
                )
                continue
        else:
            logger.info(
                "WHATSAPP_ENABLED=false, not sending reservation reminder to %s",
                mask_wa_id(wa_id),
            )
        await _mark_sent(reservation_id)
        sent += 1
    return sent


async def reminder_loop() -> None:
    """Runs forever until cancelled: one `send_due_reminders` pass every
    `REMINDER_INTERVAL_SECONDS`. A failed pass is logged, never raised, so one bad tick never
    kills the loop."""
    while True:
        try:
            await send_due_reminders()
        except Exception:
            logger.exception("Reminder loop iteration failed")
        await asyncio.sleep(REMINDER_INTERVAL_SECONDS)
