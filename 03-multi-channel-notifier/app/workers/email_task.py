"""Email channel task (DECISIONES-03 N7): one Celery task per notification, sending to all
`recipients.email` addresses in a single SMTP message.
"""

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.workers.celery_app import celery_app
from app.workers.common import (
    PermanentDeliveryError,
    TransientDeliveryError,
    log_delivery_attempt,
    retry_countdown,
)

CHANNEL = "email"


def _send(recipients: list[str], subject: str, text_body: str, html_body: str | None) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = ", ".join(recipients)
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        assert settings.SMTP_SERVER is not None  # guaranteed by configured_channels (N6)
        assert settings.SMTP_PORT is not None
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10) as smtp:
            # Only authenticate if the server actually advertises AUTH (mailpit in dev doesn't).
            if smtp.has_extn("auth") and settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (
        TimeoutError,
        ConnectionError,
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPConnectError,
        smtplib.SMTPHeloError,
    ) as exc:
        # NB: smtplib.SMTPException subclasses OSError, so a bare `OSError` here would also
        # catch (and mis-classify as transient) permanent errors like SMTPRecipientsRefused —
        # only genuine socket-level errors and the explicitly-transient SMTP exceptions above
        # belong in this branch.
        raise TransientDeliveryError(f"SMTP transient error: {type(exc).__name__}") from exc
    except smtplib.SMTPResponseException as exc:
        if exc.smtp_code // 100 == 4:
            raise TransientDeliveryError(f"SMTP 4xx: {exc.smtp_code}") from exc
        raise PermanentDeliveryError(f"SMTP {exc.smtp_code}") from exc
    except smtplib.SMTPException as exc:
        raise PermanentDeliveryError(f"SMTP error: {type(exc).__name__}") from exc


@celery_app.task(
    bind=True,
    name="tasks.send_email",
    max_retries=5,
    retry_backoff=True,
    retry_jitter=True,
)
def send_email_task(
    self,
    notification_id: str,
    recipients: list[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    attempt_number = self.request.retries + 1
    try:
        _send(recipients, subject, text_body, html_body)
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
