"""Telegram channel task (DECISIONES-03 N7): one `sendMessage` call per chat id, all inside the
same Celery task for the notification (one `delivery_logs` row per attempt, per channel — not
per chat id).

`TELEGRAM_BOT_TOKEN` only ever appears inside the request URL built here, which is never logged
or included in an error message (N3).
"""

from app.config import settings
from app.workers.celery_app import celery_app
from app.workers.common import (
    PermanentDeliveryError,
    TransientDeliveryError,
    log_delivery_attempt,
    post_webhook_json,
    retry_countdown,
)

CHANNEL = "telegram"


def _send_to_all(chat_ids: list[str], text_body: str) -> None:
    url = f"{settings.TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    transient_errors: list[str] = []
    permanent_errors: list[str] = []
    for chat_id in chat_ids:
        try:
            post_webhook_json(url, {"chat_id": chat_id, "text": text_body})
        except TransientDeliveryError as exc:
            transient_errors.append(str(exc))
        except PermanentDeliveryError as exc:
            permanent_errors.append(str(exc))

    if transient_errors:
        # Retrying the whole task may re-send to chat ids that already succeeded; acceptable
        # for a notification hub (at-least-once delivery) and far simpler than per-recipient
        # retry state, which the `delivery_logs` schema (one row per channel attempt) has no
        # room for anyway.
        raise TransientDeliveryError(f"{len(transient_errors)} chat id(s) failed transiently")
    if permanent_errors:
        raise PermanentDeliveryError(f"{len(permanent_errors)} chat id(s) rejected")


@celery_app.task(
    bind=True,
    name="tasks.send_telegram",
    max_retries=5,
    retry_backoff=True,
    retry_jitter=True,
    rate_limit="30/s",
)
def send_telegram_task(self, notification_id: str, chat_ids: list[str], text_body: str) -> None:
    attempt_number = self.request.retries + 1
    try:
        _send_to_all(chat_ids, text_body)
    except PermanentDeliveryError as exc:
        log_delivery_attempt(notification_id, CHANNEL, "failed", attempt_number, str(exc))
    except TransientDeliveryError as exc:
        if self.request.retries >= self.max_retries:
            log_delivery_attempt(notification_id, CHANNEL, "failed", attempt_number, str(exc))
            return
        log_delivery_attempt(notification_id, CHANNEL, "retrying", attempt_number, str(exc))
        raise self.retry(exc=exc, countdown=retry_countdown(self.request.retries)) from exc
    else:
        log_delivery_attempt(notification_id, CHANNEL, "delivered", attempt_number)
