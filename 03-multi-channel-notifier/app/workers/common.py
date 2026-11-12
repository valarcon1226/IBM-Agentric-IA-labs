"""Shared helpers for the per-channel Celery tasks (DECISIONES-03 N7).

Synchronous SQL (psycopg, one short-lived connection per call) is intentional here: Celery
workers are separate sync processes from the async FastAPI app, so they do not share
`app.database`'s asyncpg engine.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Literal

import psycopg
from celery.utils.time import get_exponential_backoff_interval

from app.config import settings

logger = logging.getLogger(__name__)

DeliveryStatus = Literal["delivered", "retrying", "failed"]

# README §5 / DECISIONES-03 N7: high=0, medium=5, low=9 (approximate under Redis).
PRIORITY_TO_CELERY = {"high": 0, "medium": 5, "low": 9}

HTTP_TIMEOUT_SECONDS = 5.0

# Same cap and factor Celery's own `retry_backoff=True` machinery uses by default (10 minutes).
RETRY_BACKOFF_MAX_SECONDS = 600


def retry_countdown(retries: int) -> int:
    """Compute the countdown (seconds) for a manual `self.retry(countdown=...)` call.

    Celery's `retry_backoff`/`retry_jitter` task options only take effect when the retry is
    triggered by `autoretry_for`. These tasks retry manually (see module docstrings in
    `email_task.py` et al. for why), so the exponential-backoff-with-full-jitter countdown has to
    be computed here and passed explicitly — otherwise `Task.retry()` falls back to the fixed
    `default_retry_delay` (180s, no backoff, no jitter), which violates DECISIONES-03 N7.
    """
    return get_exponential_backoff_interval(
        factor=1, retries=retries, maximum=RETRY_BACKOFF_MAX_SECONDS, full_jitter=True
    )


class TransientDeliveryError(Exception):
    """A retryable failure: network error, timeout, HTTP 429, or HTTP 5xx."""


class PermanentDeliveryError(Exception):
    """A non-retryable failure: any other 4xx response or a rejected message."""


def get_connection() -> psycopg.Connection:
    # psycopg3 accepts the same postgresql:// DSN used by the async (asyncpg) engine as-is.
    return psycopg.connect(settings.DATABASE_URL, autocommit=True, connect_timeout=5)


def log_delivery_attempt(
    notification_id: str,
    channel: str,
    status: DeliveryStatus,
    attempt_number: int,
    error_message: str | None = None,
) -> None:
    """Insert one `delivery_logs` row for this attempt, then recompute `notifications.status`.

    The status recompute is a single `UPDATE ... FROM (...)` statement driven entirely by the
    current contents of `delivery_logs`, so concurrent channel tasks for the same notification
    never race each other into an inconsistent status (DECISIONES-03 N7).
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO delivery_logs "
            "(notification_id, channel, status, attempt_number, error_message) "
            "VALUES (%s, %s, %s, %s, %s)",
            (notification_id, channel, status, attempt_number, error_message),
        )
        cur.execute(
            """
            WITH requested AS (
                SELECT jsonb_object_keys(recipients) AS channel
                FROM notifications WHERE id = %(id)s
            ),
            latest AS (
                SELECT DISTINCT ON (channel) channel, status
                FROM delivery_logs
                WHERE notification_id = %(id)s
                ORDER BY channel, log_id DESC
            ),
            joined AS (
                SELECT r.channel, l.status
                FROM requested r
                LEFT JOIN latest l ON l.channel = r.channel
            ),
            computed AS (
                SELECT
                    CASE
                        WHEN COUNT(*) FILTER (WHERE status IS DISTINCT FROM 'delivered') = 0
                            THEN 'completed'
                        WHEN COUNT(*) FILTER (WHERE status = 'failed') > 0 THEN 'failed'
                        ELSE 'queued'
                    END AS new_status
                FROM joined
            )
            UPDATE notifications
            SET status = computed.new_status, updated_at = NOW()
            FROM computed
            WHERE id = %(id)s
            """,
            {"id": notification_id},
        )


def post_webhook_json(url: str, payload: dict[str, object]) -> None:
    """POST a JSON body to a webhook URL, classifying failures as transient or permanent.

    Never include `url` in a raised message: callers only ever get the HTTP status code or the
    exception type name, never the (potentially token-bearing) URL itself (DECISIONES-03 N3).
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            _raise_for_http_status(response.status)
    except urllib.error.HTTPError as exc:
        _raise_for_http_status(exc.code)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise TransientDeliveryError(f"Network error: {type(exc).__name__}") from exc


def _raise_for_http_status(status_code: int) -> None:
    if status_code >= 400:
        if status_code == 429 or status_code >= 500:
            raise TransientDeliveryError(f"HTTP {status_code}")
        raise PermanentDeliveryError(f"HTTP {status_code}")
