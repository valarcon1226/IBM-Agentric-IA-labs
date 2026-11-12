"""Integration and E2E tests against the real docker-compose stack (DECISIONES-03 N9).

These tests talk to the actual API container (http://localhost:8003), the real Postgres
(localhost:5435) and the real mailpit SMTP-sink UI (http://localhost:8026) started by
``docker compose``. Connection settings are read from ``E2E_*`` environment variables, falling
back to the values documented in ``.env.example``, and the whole module skips cleanly (instead
of failing) when the stack is not reachable so the unit suite still runs without Docker.

Only stdlib ``urllib`` and the already-pinned ``psycopg`` are used (same tools as
``app/workers/common.py``) — no new dependency, following the project's `02` E2E pattern
(``02-business-registry-enricher/tests/test_integration_e2e.py``) of discrete connection
keyword arguments (never a single credentialed DSN string).

Every row/message a test creates is deleted again at the end of the test (``notifications``
cascades to ``delivery_logs`` via ``ON DELETE CASCADE``, see ``init-db.sql``).
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.integration

## NOTE: dedicated E2E_* names (see 02's test_integration_e2e.py) instead of the bare
## DATABASE_URL/API_KEY/etc. names, which tests/conftest.py already points at unit-test
## fallback values for the mocked suite.
API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://localhost:8003")
API_KEY = os.environ.get("E2E_API_KEY", "change_me_api_key")
MAILPIT_BASE_URL = os.environ.get("E2E_MAILPIT_BASE_URL", "http://localhost:8026")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

POSTGRES_HOST = os.environ.get("E2E_POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("E2E_POSTGRES_PORT", "5435"))
POSTGRES_USER = os.environ.get("E2E_POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("E2E_POSTGRES_PASSWORD", "change_me_postgres_password")
POSTGRES_DB = os.environ.get("E2E_POSTGRES_DB", "notifier_db")

POLL_TIMEOUT_SECONDS = 20
POLL_INTERVAL_SECONDS = 0.5
HTTP_TIMEOUT_SECONDS = 5.0
TERMINAL_STATUSES = {"completed", "failed"}


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


def _delete_notification(notification_id: str) -> None:
    # `delivery_logs.notification_id` is `ON DELETE CASCADE` (init-db.sql), so this alone
    # removes every row this test created.
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM notifications WHERE id = %s", (notification_id,))


def _http(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{API_BASE_URL}{path}", data=data, headers=HEADERS, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


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


def _poll_until_terminal(notification_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    status_code, body = _http("GET", f"/api/v1/notifications/{notification_id}")
    while body.get("status") not in TERMINAL_STATUSES:
        if time.monotonic() > deadline:
            pytest.fail(f"Notification {notification_id} did not reach a terminal status: {body}")
        time.sleep(POLL_INTERVAL_SECONDS)
        status_code, body = _http("GET", f"/api/v1/notifications/{notification_id}")
    assert status_code == 200
    return body


@pytest.fixture(scope="module")
def stack() -> str:
    try:
        with urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=2) as response:
            if response.status != 200:
                pytest.skip(f"Docker stack not healthy at {API_BASE_URL}: HTTP {response.status}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"Docker stack not reachable at {API_BASE_URL}: {exc}")
    return API_BASE_URL


def test_health_endpoint_reports_healthy(stack: str) -> None:
    status_code, body = _http("GET", "/health")
    # /health is deliberately unauthenticated (DECISIONES-03 N3), so this call carries the
    # Bearer header for free but doesn't need it.
    assert status_code == 200
    assert body == {"status": "healthy"}


@pytest.mark.e2e
def test_email_slack_notification_delivers_and_completes(stack: str) -> None:
    email_address = f"e2e-{uuid.uuid4().hex[:10]}@example.com"
    status_code, body = _http(
        "POST",
        "/api/v1/notify",
        {
            "template_name": "welcome_email",
            "channels": ["email", "slack"],
            "priority": "high",
            "recipients": {"email": [email_address], "slack": ["#e2e-alerts"]},
            "payload": {"user_name": "E2E Tester", "system": "E2E Suite"},
        },
    )
    assert status_code == 200, body
    notification_id = body["notification_id"]
    assert body["status"] == "queued"

    mailpit_ids: list[str] = []
    try:
        detail = _poll_until_terminal(notification_id)
        assert detail["status"] == "completed"
        delivery_logs = detail["delivery_logs"]
        assert len(delivery_logs) == 2
        assert {log["channel"] for log in delivery_logs} == {"email", "slack"}
        assert all(log["status"] == "delivered" for log in delivery_logs)

        # Exactly 2 `delivery_logs` rows, both delivered — verified again straight from
        # Postgres, independently of what the API reports.
        with _pg_connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM delivery_logs WHERE notification_id = %s", (notification_id,)
            )
            rows = cur.fetchall()
        assert len(rows) == 2
        assert all(row[0] == "delivered" for row in rows)

        # The email is really visible in mailpit's API.
        messages = _mailpit_search(email_address)
        assert len(messages) == 1
        mailpit_ids = [message["ID"] for message in messages]

        # `GET /notifications/{id}` returns it.
        status_code, single = _http("GET", f"/api/v1/notifications/{notification_id}")
        assert status_code == 200
        assert single["id"] == notification_id
        assert single["status"] == "completed"

        # `GET /notifications?status=completed` returns it too.
        status_code, listing = _http("GET", "/api/v1/notifications?status=completed&limit=200")
        assert status_code == 200
        assert notification_id in {item["id"] for item in listing["results"]}
    finally:
        _mailpit_delete(mailpit_ids)
        _delete_notification(notification_id)


@pytest.mark.e2e
def test_four_channel_notification_reaches_completed(stack: str) -> None:
    email_address = f"e2e-{uuid.uuid4().hex[:10]}@example.com"
    status_code, body = _http(
        "POST",
        "/api/v1/notify",
        {
            "template_name": "welcome_email",
            "channels": ["email", "slack", "telegram", "discord"],
            "priority": "medium",
            "recipients": {
                "email": [email_address],
                "telegram": ["123456789"],
                "slack": ["#e2e-alerts"],
                "discord": ["#e2e-alerts"],
            },
            "payload": {"user_name": "E2E Tester", "system": "E2E Suite (4 channels)"},
        },
    )
    assert status_code == 200, body
    notification_id = body["notification_id"]

    mailpit_ids: list[str] = []
    try:
        detail = _poll_until_terminal(notification_id)
        assert detail["status"] == "completed"
        delivery_logs = detail["delivery_logs"]
        assert len(delivery_logs) == 4
        assert {log["channel"] for log in delivery_logs} == {
            "email",
            "slack",
            "telegram",
            "discord",
        }
        assert all(log["status"] == "delivered" for log in delivery_logs)

        messages = _mailpit_search(email_address)
        mailpit_ids = [message["ID"] for message in messages]
    finally:
        _mailpit_delete(mailpit_ids)
        _delete_notification(notification_id)
