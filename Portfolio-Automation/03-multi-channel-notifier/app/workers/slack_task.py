"""Slack channel task (DECISIONES-03 N7): one webhook POST per notification.

The destination is always `settings.SLACK_WEBHOOK_URL` — never a URL taken from the request
(no SSRF, N3).
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

CHANNEL = "slack"


@celery_app.task(
    bind=True,
    name="tasks.send_slack",
    max_retries=5,
    retry_backoff=True,
    retry_jitter=True,
    rate_limit="1/s",
)
def send_slack_task(self, notification_id: str, text_body: str) -> None:
    attempt_number = self.request.retries + 1
    try:
        assert settings.SLACK_WEBHOOK_URL is not None  # guaranteed by configured_channels (N6)
        post_webhook_json(settings.SLACK_WEBHOOK_URL, {"text": text_body})
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
