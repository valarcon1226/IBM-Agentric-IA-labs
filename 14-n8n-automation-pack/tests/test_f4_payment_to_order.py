"""Integration tests for F4 (payment webhook -> mark order paid -> notify) against the real
docker-compose stack (DECISIONES-14 A6). Skips cleanly if the stack isn't reachable. Talks to the
real n8n webhook (``http://localhost:5680``), the real Postgres (``localhost:5437``) and the real
mailpit API (``http://localhost:8027``).

Every row a test creates is deleted again at the end of the test.
"""

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

import psycopg
import pytest

from tests.conftest import (
    HTTP_TIMEOUT_SECONDS,
    MAILPIT_BASE_URL,
    N8N_BASE_URL,
    PAYMENT_WEBHOOK_SECRET,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

pytestmark = pytest.mark.integration

WEBHOOK_PATH = "/webhook/payment-webhook"


def _pg_connect() -> psycopg.Connection:
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
        autocommit=True,
        connect_timeout=5,
    )


def _insert_pending_order(email: str) -> int:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO orders (customer_name, customer_email, total_cop, status) "
            "VALUES (%s, %s, %s, 'pending') RETURNING id",
            ("Pytest Cliente", email, 75000),
        )
        (order_id,) = cur.fetchone()
    return order_id


def _order_status(order_id: int) -> str | None:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        row = cur.fetchone()
    return row[0] if row else None


def _cleanup_order(order_id: int, event_id: str) -> None:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        cur.execute("DELETE FROM processed_events WHERE event_id = %s", (event_id,))


def _sign(raw_body: bytes) -> str:
    digest = hmac.new(PAYMENT_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _post_payment(payload: dict[str, Any], signature: str | None) -> tuple[int, Any, bytes]:
    raw_body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Signature"] = signature
    request = urllib.request.Request(
        f"{N8N_BASE_URL}{WEBHOOK_PATH}", data=raw_body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read()), raw_body
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else {}), raw_body


def _mailpit_search(to_address: str) -> list[dict[str, Any]]:
    query = urllib.parse.quote(f"to:{to_address}")
    with urllib.request.urlopen(
        f"{MAILPIT_BASE_URL}/api/v1/search?query={query}", timeout=HTTP_TIMEOUT_SECONDS
    ) as response:
        return json.loads(response.read())["messages"]


def _mailpit_delete(message_ids: list[str]) -> None:
    if not message_ids:
        return
    data = json.dumps({"IDs": message_ids}).encode("utf-8")
    request = urllib.request.Request(
        f"{MAILPIT_BASE_URL}/api/v1/messages",
        data=data,
        headers={"Content-Type": "application/json"},
        method="DELETE",
    )
    urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS)


@pytest.fixture(scope="module")
def stack() -> str:
    try:
        with urllib.request.urlopen(f"{N8N_BASE_URL}/healthz", timeout=2) as response:
            if response.status != 200:
                pytest.skip(f"n8n not healthy at {N8N_BASE_URL}: HTTP {response.status}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"n8n stack not reachable at {N8N_BASE_URL}: {exc}")
    return N8N_BASE_URL


def _event_payload(order_id: int, event_id: str) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "payment.succeeded",
        "data": {"order_id": order_id, "amount_cop": 75000},
    }


def test_valid_payment_marks_order_paid_and_notifies(stack: str) -> None:
    email = f"order-{uuid.uuid4().hex[:10]}@example.com"
    event_id = f"evt_{uuid.uuid4().hex}"
    order_id = _insert_pending_order(email)
    mailpit_ids: list[str] = []
    try:
        payload = _event_payload(order_id, event_id)
        raw_body = json.dumps(payload).encode("utf-8")
        status_code, body, _ = _post_payment(payload, _sign(raw_body))
        assert status_code == 200, body
        assert body["status"] == "ok"
        assert body["order_id"] == order_id

        assert _order_status(order_id) == "paid"

        messages = _mailpit_search(email)
        assert len(messages) == 1
        mailpit_ids = [message["ID"] for message in messages]
    finally:
        _mailpit_delete(mailpit_ids)
        _cleanup_order(order_id, event_id)


def test_duplicate_event_id_is_ignored_and_order_stays_paid_once(stack: str) -> None:
    email = f"order-{uuid.uuid4().hex[:10]}@example.com"
    event_id = f"evt_{uuid.uuid4().hex}"
    order_id = _insert_pending_order(email)
    mailpit_ids: list[str] = []
    try:
        payload = _event_payload(order_id, event_id)
        status_code, body, _ = _post_payment(payload, _sign(json.dumps(payload).encode("utf-8")))
        assert status_code == 200, body
        assert body["status"] == "ok"

        # Same event id retried (e.g. webhook provider retry): must not re-process.
        status_code, body, _ = _post_payment(payload, _sign(json.dumps(payload).encode("utf-8")))
        assert status_code == 200, body
        assert body["status"] == "ignored"
        assert body["reason"] == "duplicate_event"

        assert _order_status(order_id) == "paid"
        messages = _mailpit_search(email)
        assert len(messages) == 1  # only the first (valid, new) event sends an email
        mailpit_ids = [message["ID"] for message in messages]
    finally:
        _mailpit_delete(mailpit_ids)
        _cleanup_order(order_id, event_id)


def test_invalid_signature_is_rejected_and_order_untouched(stack: str) -> None:
    email = f"order-{uuid.uuid4().hex[:10]}@example.com"
    event_id = f"evt_{uuid.uuid4().hex}"
    order_id = _insert_pending_order(email)
    try:
        payload = _event_payload(order_id, event_id)
        status_code, body, _ = _post_payment(payload, "sha256=" + "0" * 64)
        assert status_code == 401, body
        assert body["status"] == "error"

        assert _order_status(order_id) == "pending"
        with _pg_connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM processed_events WHERE event_id = %s", (event_id,))
            (count,) = cur.fetchone()
        assert count == 0
    finally:
        _cleanup_order(order_id, event_id)


def test_missing_signature_header_is_rejected(stack: str) -> None:
    email = f"order-{uuid.uuid4().hex[:10]}@example.com"
    event_id = f"evt_{uuid.uuid4().hex}"
    order_id = _insert_pending_order(email)
    try:
        payload = _event_payload(order_id, event_id)
        status_code, body, _ = _post_payment(payload, signature=None)
        assert status_code == 401, body
        assert _order_status(order_id) == "pending"
    finally:
        _cleanup_order(order_id, event_id)


def test_already_paid_order_is_ignored(stack: str) -> None:
    email = f"order-{uuid.uuid4().hex[:10]}@example.com"
    event_id = f"evt_{uuid.uuid4().hex}"
    order_id = _insert_pending_order(email)
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orders SET status = 'paid' WHERE id = %s", (order_id,))
    try:
        payload = _event_payload(order_id, event_id)
        status_code, body, _ = _post_payment(payload, _sign(json.dumps(payload).encode("utf-8")))
        assert status_code == 200, body
        assert body["status"] == "ignored"
        assert body["reason"] == "order_not_found_or_already_paid"
    finally:
        _cleanup_order(order_id, event_id)


def test_nonexistent_order_is_ignored(stack: str) -> None:
    event_id = f"evt_{uuid.uuid4().hex}"
    order_id = 999_999_999
    try:
        payload = _event_payload(order_id, event_id)
        status_code, body, _ = _post_payment(payload, _sign(json.dumps(payload).encode("utf-8")))
        assert status_code == 200, body
        assert body["status"] == "ignored"
        assert body["reason"] == "order_not_found_or_already_paid"
    finally:
        with _pg_connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM processed_events WHERE event_id = %s", (event_id,))
