"""W10 integration/E2E tests (DECISIONES-13): exercise the real running stack (Postgres + API)
through `/dev/chat` with `LLM_FAKE=true`, verifying each flow lands correctly in the database.

Excluded by default (see `pyproject.toml`'s `addopts`); run explicitly with:

    pytest -m "integration or e2e"

against a stack started with a one-off `LLM_FAKE=true` override, e.g.:

    docker compose --env-file .env.example run -e LLM_FAKE=true ...  (see docs/reviews for the
    exact one-off override used in this batch)

If the API isn't reachable at `E2E_BASE_URL` (default `http://localhost:8004`), every test in
this module is skipped cleanly — no stack required to collect or to run the rest of the suite.
"""

import datetime as dt
import json
import secrets
import uuid

import asyncpg
import httpx
import pytest

pytestmark = pytest.mark.e2e

E2E_BASE_URL = "http://localhost:8004"
E2E_DEV_API_KEY = "change_me_dev_api_key"  # value of DEV_API_KEY in .env.example

# Matches POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB/the published port in .env.example and
# docker-compose.yml for this project's local stack (not a production credential).
_DB_HOST = "localhost"
_DB_PORT = 5436
_DB_USER = "postgres"
_DB_PASSWORD = "change_me_postgres_password"
_DB_NAME = "restaurant_db"


def _stack_reachable() -> bool:
    try:
        response = httpx.get(f"{E2E_BASE_URL}/health", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(autouse=True, scope="module")
def _require_stack():
    if not _stack_reachable():
        pytest.skip(f"Stack not reachable at {E2E_BASE_URL}; skipping E2E tests.")


def _new_wa_id() -> str:
    return "5730099" + secrets.token_hex(4)[:7]


async def _dev_chat(wa_id: str, script: dict) -> list[str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{E2E_BASE_URL}/dev/chat",
            headers={"Authorization": f"Bearer {E2E_DEV_API_KEY}"},
            json={"wa_id": wa_id, "text": json.dumps(script)},
        )
        response.raise_for_status()
        return response.json()["replies"]


def _next_valid_reservation_date() -> dt.date:
    """First date at least 2 days out that isn't a Monday (DECISIONES-13 W6 reservation rules:
    closed Mondays)."""
    candidate = dt.date.today() + dt.timedelta(days=2)
    while candidate.weekday() == 0:
        candidate += dt.timedelta(days=1)
    return candidate


async def _db_connection() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=_DB_HOST, port=_DB_PORT, user=_DB_USER, password=_DB_PASSWORD, database=_DB_NAME
    )


async def test_delivery_order_lands_with_the_correct_total_in_the_database():
    wa_id = _new_wa_id()
    script = {
        "tool": "create_order",
        "arguments": {
            "items": [{"dish_id": 1, "qty": 1}],
            "address": "Calle 10 #5-20",
            "zone": "Chapinero",
            "payment_method": "contraentrega",
        },
    }

    replies = await _dev_chat(wa_id, script)
    assert replies  # the fake LLM always summarizes the tool result

    connection = await _db_connection()
    try:
        row = await connection.fetchrow(
            "SELECT total_cop, status FROM orders WHERE wa_id = $1 "
            "ORDER BY created_at DESC LIMIT 1",
            wa_id,
        )
    finally:
        await connection.close()

    assert row is not None
    # Bandeja Paisa (34000 COP) x1 + Chapinero delivery fee (5000 COP) = 39000 COP.
    assert row["total_cop"] == 39000
    assert row["status"] == "pending"


async def test_reservation_lands_in_the_database():
    wa_id = _new_wa_id()
    reservation_date = _next_valid_reservation_date()
    script = {
        "tool": "create_reservation",
        "arguments": {"date": reservation_date.isoformat(), "time": "13:00", "party_size": 2},
    }

    replies = await _dev_chat(wa_id, script)
    assert replies

    connection = await _db_connection()
    try:
        row = await connection.fetchrow(
            "SELECT reservation_date, reservation_time, party_size, status FROM reservations "
            "WHERE wa_id = $1 ORDER BY created_at DESC LIMIT 1",
            wa_id,
        )
    finally:
        await connection.close()

    assert row is not None
    assert row["reservation_date"] == reservation_date
    assert row["party_size"] == 2
    assert row["status"] == "confirmed"


async def test_event_request_creates_a_lead_and_pauses_the_bot_via_handover():
    wa_id = _new_wa_id()
    event_date = dt.date.today() + dt.timedelta(days=30)

    lead_script = {
        "tool": "register_event_lead",
        "arguments": {
            "event_type": "matrimonio",
            "date": event_date.isoformat(),
            "guests": 80,
            "budget": 8000000,
            "contact_name": f"Cliente E2E {uuid.uuid4().hex[:6]}",
        },
    }
    lead_replies = await _dev_chat(wa_id, lead_script)
    assert lead_replies

    handover_script = {
        "tool": "handover_to_human",
        "arguments": {"reason": "Quiere coordinar un evento grande con un humano."},
    }
    handover_replies = await _dev_chat(wa_id, handover_script)
    assert handover_replies

    connection = await _db_connection()
    try:
        lead_row = await connection.fetchrow(
            "SELECT id FROM event_leads WHERE wa_id = $1 ORDER BY created_at DESC LIMIT 1", wa_id
        )
        handover_row = await connection.fetchrow(
            "SELECT id FROM handovers WHERE wa_id = $1 AND active = TRUE "
            "ORDER BY created_at DESC LIMIT 1",
            wa_id,
        )
    finally:
        await connection.close()

    assert lead_row is not None
    assert handover_row is not None

    # Bot stays silent for this customer while the handover is active (W7): a normal text
    # message now gets no replies at all. Plain, non-JSON text exercises the "handover active ->
    # stay silent" branch in app.conversation without needing the fake LLM to recognize anything.
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{E2E_BASE_URL}/dev/chat",
            headers={"Authorization": f"Bearer {E2E_DEV_API_KEY}"},
            json={"wa_id": wa_id, "text": "Hola, ¿siguen ahí?"},
        )
        response.raise_for_status()
        silent_replies = response.json()["replies"]

    assert silent_replies == []
