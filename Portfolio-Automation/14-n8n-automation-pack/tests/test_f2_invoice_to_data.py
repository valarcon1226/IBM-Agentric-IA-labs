"""Integration tests for F2 (invoice PDF -> data) against the real docker-compose stack
(DECISIONES-14 A6/B2). Skips cleanly if the stack isn't reachable. Talks to the real n8n webhook
(``http://localhost:5680``), the real Postgres (``localhost:5437``), the real mailpit API
(``http://localhost:8027``) and the real fake-llm (through n8n, never called directly).

Every row/email a test creates is deleted again at the end of the test.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
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

WEBHOOK_PATH = "/webhook/invoice-upload"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
TEAM_EMAIL = "equipo@sabordecasa.local"


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


def _delete_invoice(invoice_id: int) -> None:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))


def _invoice_row(invoice_id: int) -> tuple | None:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT provider_name, provider_nit, invoice_date, subtotal_cop, iva_cop, total_cop, "
            "status FROM invoices WHERE id = %s",
            (invoice_id,),
        )
        return cur.fetchone()


def _post_invoice(pdf_path: Path, api_key: str | None) -> tuple[int, Any]:
    data = pdf_path.read_bytes()
    headers = {"Content-Type": "application/pdf"}
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


def _mailpit_search_team(subject_contains: str) -> list[dict[str, Any]]:
    query = urllib.parse.quote(f"to:{TEAM_EMAIL}")
    with urllib.request.urlopen(
        f"{MAILPIT_BASE_URL}/api/v1/search?query={query}", timeout=HTTP_TIMEOUT_SECONDS
    ) as response:
        messages = json.loads(response.read())["messages"]
    return [m for m in messages if subject_contains in m["Subject"]]


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


def test_valid_invoice_is_validated_and_stored(stack: str) -> None:
    status_code, body = _post_invoice(SAMPLES_DIR / "factura-valida.pdf", WEBHOOK_API_KEY)
    invoice_id = body.get("invoice_id")
    try:
        assert status_code == 200, body
        assert body["status"] == "validated"
        assert isinstance(invoice_id, int)

        row = _invoice_row(invoice_id)
        assert row is not None
        provider_name, provider_nit, invoice_date, subtotal, iva, total, status = row
        assert provider_name == "Distribuidora La Sabana SAS"
        assert provider_nit == "900123456-7"
        assert str(invoice_date) == "2026-09-30"
        assert (subtotal, iva, total) == (195000, 37050, 232050)
        assert status == "validated"
    finally:
        if isinstance(invoice_id, int):
            _delete_invoice(invoice_id)


def test_bad_totals_invoice_needs_review_and_notifies_team(stack: str) -> None:
    status_code, body = _post_invoice(
        SAMPLES_DIR / "factura-totales-no-cuadran.pdf", WEBHOOK_API_KEY
    )
    invoice_id = body.get("invoice_id")
    mailpit_ids: list[str] = []
    try:
        assert status_code == 200, body
        assert body["status"] == "needs_review"
        assert "total does not match subtotal + iva" in body["errors"]
        assert isinstance(invoice_id, int)

        row = _invoice_row(invoice_id)
        assert row is not None
        assert row[-1] == "needs_review"

        messages = _mailpit_search_team(f"Factura #{invoice_id}")
        assert len(messages) == 1
        mailpit_ids = [m["ID"] for m in messages]
    finally:
        _mailpit_delete(mailpit_ids)
        if isinstance(invoice_id, int):
            _delete_invoice(invoice_id)


def test_bad_date_invoice_needs_review(stack: str) -> None:
    status_code, body = _post_invoice(
        SAMPLES_DIR / "factura-fecha-invalida.pdf", WEBHOOK_API_KEY
    )
    invoice_id = body.get("invoice_id")
    mailpit_ids: list[str] = []
    try:
        assert status_code == 200, body
        assert body["status"] == "needs_review"
        assert "fecha is invalid" in body["errors"]

        row = _invoice_row(invoice_id)
        assert row is not None
        assert row[2] is None  # invalid date is stored as NULL, never garbage in a DATE column
        assert row[-1] == "needs_review"

        messages = _mailpit_search_team(f"Factura #{invoice_id}")
        mailpit_ids = [m["ID"] for m in messages]
    finally:
        _mailpit_delete(mailpit_ids)
        if isinstance(invoice_id, int):
            _delete_invoice(invoice_id)


def test_missing_api_key_is_rejected(stack: str) -> None:
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM invoices")
        (count_before,) = cur.fetchone()

    status_code, _ = _post_invoice(SAMPLES_DIR / "factura-valida.pdf", api_key=None)
    assert status_code == 403

    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM invoices")
        (count_after,) = cur.fetchone()
    assert count_after == count_before


def test_wrong_api_key_is_rejected(stack: str) -> None:
    status_code, _ = _post_invoice(SAMPLES_DIR / "factura-valida.pdf", api_key="wrong-key")
    assert status_code == 403
