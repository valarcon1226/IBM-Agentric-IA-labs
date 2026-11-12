"""Integration tests for F1 (lead form -> CRM) against the real docker-compose stack
(DECISIONES-14 A6). Skips cleanly if the stack isn't reachable so the unit suite still runs
without Docker. Talks to the real n8n webhook (``http://localhost:5680``), the real Postgres
(``localhost:5437``) and the real mailpit API (``http://localhost:8027``).

Every row a test creates is deleted again at the end of the test.
"""

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
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
    WEBHOOK_API_KEY,
)

pytestmark = pytest.mark.integration

WEBHOOK_PATH = "/webhook/lead-form"


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


def _delete_lead(email: str) -> None:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM crm_leads WHERE email = %s", (email,))


def _post(path: str, body: dict[str, Any], api_key: str | None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["X-Api-Key"] = api_key
    request = urllib.request.Request(
        f"{N8N_BASE_URL}{path}", data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        if not raw:
            return exc.code, {}
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode("utf-8", errors="replace")}


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


def _lead_payload(email: str) -> dict[str, Any]:
    return {
        "name": "Valentina Restrepo",
        "email": email,
        "phone": "3001234567",
        "event_type": "cumpleaños",
        "event_date": "2026-03-15",
        "guests": 12,
        "message": "Quisiéramos el salón grande.",
    }


def test_valid_lead_is_created_emailed_and_notified(stack: str) -> None:
    email = f"lead-{uuid.uuid4().hex[:10]}@example.com"
    mailpit_ids: list[str] = []
    try:
        status_code, body = _post(WEBHOOK_PATH, _lead_payload(email), WEBHOOK_API_KEY)
        assert status_code == 200, body
        assert body["status"] == "created"
        assert isinstance(body["lead_id"], int)

        with _pg_connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, email, event_type, guests FROM crm_leads WHERE email = %s", (email,)
            )
            row = cur.fetchone()
        assert row is not None
        assert row == ("Valentina Restrepo", email, "cumpleaños", 12)

        messages = _mailpit_search(email)
        assert len(messages) == 1
        mailpit_ids = [message["ID"] for message in messages]
    finally:
        _mailpit_delete(mailpit_ids)
        _delete_lead(email)


def test_duplicate_lead_email_is_idempotent(stack: str) -> None:
    email = f"lead-{uuid.uuid4().hex[:10]}@example.com"
    mailpit_ids: list[str] = []
    try:
        status_code, body = _post(WEBHOOK_PATH, _lead_payload(email), WEBHOOK_API_KEY)
        assert status_code == 200, body
        first_lead_id = body["lead_id"]

        status_code, body = _post(WEBHOOK_PATH, _lead_payload(email), WEBHOOK_API_KEY)
        assert status_code == 200, body
        assert body["status"] == "duplicate"

        with _pg_connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM crm_leads WHERE email = %s", (email,))
            (count,) = cur.fetchone()
        assert count == 1

        messages = _mailpit_search(email)
        assert len(messages) == 1  # only the first (valid) call sends a welcome email
        mailpit_ids = [message["ID"] for message in messages]
        assert first_lead_id is not None
    finally:
        _mailpit_delete(mailpit_ids)
        _delete_lead(email)


def test_missing_api_key_is_rejected(stack: str) -> None:
    email = f"lead-{uuid.uuid4().hex[:10]}@example.com"
    status_code, _ = _post(WEBHOOK_PATH, _lead_payload(email), api_key=None)
    assert status_code == 403
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM crm_leads WHERE email = %s", (email,))
        (count,) = cur.fetchone()
    assert count == 0


def test_wrong_api_key_is_rejected(stack: str) -> None:
    email = f"lead-{uuid.uuid4().hex[:10]}@example.com"
    status_code, _ = _post(WEBHOOK_PATH, _lead_payload(email), api_key="wrong-key")
    assert status_code == 403
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM crm_leads WHERE email = %s", (email,))
        (count,) = cur.fetchone()
    assert count == 0


def test_invalid_payload_is_rejected_with_400(stack: str) -> None:
    status_code, body = _post(WEBHOOK_PATH, {"name": "", "email": "not-an-email"}, WEBHOOK_API_KEY)
    assert status_code == 400, body
    assert body["status"] == "error"
    assert "errors" in body and len(body["errors"]) > 0


def test_missing_email_is_rejected_with_400(stack: str) -> None:
    status_code, body = _post(WEBHOOK_PATH, {"name": "Sin Email"}, WEBHOOK_API_KEY)
    assert status_code == 400, body
    assert "email is required" in body["errors"]
