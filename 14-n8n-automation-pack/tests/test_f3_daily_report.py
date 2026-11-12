"""Integration tests for F3 (daily sales report) against the real docker-compose stack
(DECISIONES-14 A6/B3), triggered through its manual demo webhook. Skips cleanly if the stack
isn't reachable. ``webhook-sink`` has no published port (A2, same as F1/F4), so "was it
received" is checked the one way available from outside the compose network: its own stdout log,
read with ``docker compose logs`` (no new service, no port change).

Every email a test creates is deleted again at the end of the test.
"""

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
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

WEBHOOK_PATH = "/webhook/daily-report-trigger"
TEAM_EMAIL = "equipo@sabordecasa.local"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Fixed demo date seeded in init-db.sql (T-14-lote-b follow-up: CURRENT_DATE-relative seed data
# drifted out of "yesterday" after a few days). Also documented in docs/DEMO-SCRIPT.md, README.md.
DEMO_SALES_DATE = "2025-01-15"


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


def _expected_total_cop(sale_date: str | None = None) -> int:
    query = "SELECT COALESCE(SUM(total_cop), 0) FROM sales WHERE sale_date = {}".format(
        "%s" if sale_date is not None else "CURRENT_DATE - 1"
    )
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute(query, (sale_date,) if sale_date is not None else None)
        (total,) = cur.fetchone()
    return int(total)


def _post(api_key: str | None, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key is not None:
        headers["X-Api-Key"] = api_key
    request = urllib.request.Request(
        f"{N8N_BASE_URL}{WEBHOOK_PATH}", data=data, headers=headers, method="POST"
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


def _mailpit_search_team() -> list[dict[str, Any]]:
    query = urllib.parse.quote(f"to:{TEAM_EMAIL} subject:\"Reporte diario de ventas\"")
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


def _webhook_sink_logs(since: datetime) -> str:
    since_arg = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    result = subprocess.run(
        ["docker", "compose", "logs", "--no-color", "--since", since_arg, "webhook-sink"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.stdout + result.stderr


@pytest.fixture(scope="module")
def stack() -> str:
    try:
        with urllib.request.urlopen(f"{N8N_BASE_URL}/healthz", timeout=2) as response:
            if response.status != 200:
                pytest.skip(f"n8n not healthy at {N8N_BASE_URL}: HTTP {response.status}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"n8n stack not reachable at {N8N_BASE_URL}: {exc}")
    return N8N_BASE_URL


def test_manual_trigger_with_demo_date_emails_team_and_notifies_webhook_sink(stack: str) -> None:
    # Uses the fixed demo date (init-db.sql) instead of relying on real "yesterday" having sales,
    # so this test keeps passing no matter when it runs (T-14-lote-b follow-up).
    expected_total = _expected_total_cop(DEMO_SALES_DATE)
    assert expected_total > 0, "demo seed data missing/changed - update DEMO_SALES_DATE"
    since = datetime.now(UTC)
    mailpit_ids: list[str] = []
    try:
        status_code, body = _post(WEBHOOK_API_KEY, body={"date": DEMO_SALES_DATE})
        assert status_code == 200, body
        assert body["status"] == "ok"
        assert body["report_date"] == DEMO_SALES_DATE
        assert body["total_cop"] == expected_total

        messages = _mailpit_search_team()
        assert len(messages) >= 1
        mailpit_ids = [m["ID"] for m in messages]

        logs = _webhook_sink_logs(since)
        assert '"path": "/f3-daily-report"' in logs
        # the sink logs the raw request body as a JSON-escaped string (literal backslash-quote).
        assert f'\\"total_cop\\":{expected_total}' in logs
    finally:
        _mailpit_delete(mailpit_ids)


def test_manual_trigger_without_date_defaults_to_yesterday(stack: str) -> None:
    expected_total = _expected_total_cop()
    mailpit_ids: list[str] = []
    try:
        status_code, body = _post(WEBHOOK_API_KEY)
        assert status_code == 200, body
        assert body["status"] == "ok"
        assert body["total_cop"] == expected_total

        messages = _mailpit_search_team()
        mailpit_ids = [m["ID"] for m in messages]
    finally:
        _mailpit_delete(mailpit_ids)


def test_invalid_date_is_rejected_with_400(stack: str) -> None:
    status_code, body = _post(WEBHOOK_API_KEY, body={"date": "not-a-date"})
    assert status_code == 400
    assert body["status"] == "error"
    assert "date" in body["errors"][0]


def test_missing_api_key_is_rejected(stack: str) -> None:
    status_code, _ = _post(api_key=None)
    assert status_code == 403


def test_wrong_api_key_is_rejected(stack: str) -> None:
    status_code, _ = _post(api_key="wrong-key")
    assert status_code == 403
