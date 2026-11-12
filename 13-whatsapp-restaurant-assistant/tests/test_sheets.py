"""Unit tests for app.sheets (DECISIONES-13 W8): the Google Sheets sync is optional (only active
with both `GOOGLE_SERVICE_ACCOUNT_JSON` and `GOOGLE_SHEET_ID` set) and must never raise — a
failure is logged and swallowed so it can never break the conversation. No real Google API call
is ever made: `_access_token` and the HTTP layer are both mocked.
"""

import httpx
import pytest

from app import sheets


@pytest.fixture(autouse=True)
def _clear_sheets_settings(monkeypatch):
    monkeypatch.setattr(sheets.settings, "GOOGLE_SERVICE_ACCOUNT_JSON", None)
    monkeypatch.setattr(sheets.settings, "GOOGLE_SHEET_ID", None)


async def test_append_order_is_a_noop_without_credentials(monkeypatch):
    called = []
    monkeypatch.setattr(sheets, "_access_token", lambda: called.append(1) or "token")

    await sheets.append_order(
        {"order_id": 1, "total_cop": 39000, "status": "pending"}, "573001234567"
    )

    assert called == []  # never even tried to get a token


async def test_append_order_posts_the_expected_row(monkeypatch):
    monkeypatch.setattr(
        sheets.settings, "GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}'
    )
    monkeypatch.setattr(sheets.settings, "GOOGLE_SHEET_ID", "sheet-123")
    monkeypatch.setattr(sheets, "_access_token", lambda: "fake-token")

    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(200, json={"updates": {"updatedRows": 1}})

    monkeypatch.setattr(sheets.httpx, "AsyncClient", FakeAsyncClient)

    await sheets.append_order(
        {
            "order_id": 1,
            "subtotal_cop": 34000,
            "delivery_fee_cop": 5000,
            "total_cop": 39000,
            "status": "pending",
        },
        "573001234567",
    )

    assert "sheet-123" in captured["url"]
    assert "Pedidos" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer fake-token"
    assert captured["json"]["values"] == [[1, "573001234567", 34000, 5000, 39000, "pending"]]


async def test_append_reservation_posts_expected_row(monkeypatch):
    monkeypatch.setattr(
        sheets.settings, "GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}'
    )
    monkeypatch.setattr(sheets.settings, "GOOGLE_SHEET_ID", "sheet-123")
    monkeypatch.setattr(sheets, "_access_token", lambda: "fake-token")

    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return httpx.Response(200, json={})

    monkeypatch.setattr(sheets.httpx, "AsyncClient", FakeAsyncClient)

    await sheets.append_reservation(
        {
            "reservation_id": 7,
            "date": "2026-10-10",
            "time": "19:00",
            "party_size": 4,
            "status": "confirmed",
        },
        "573004445566",
    )

    assert "Reservas" in captured["url"]
    assert captured["json"]["values"] == [
        [7, "573004445566", "2026-10-10", "19:00", 4, "confirmed"]
    ]


async def test_append_event_lead_posts_expected_row(monkeypatch):
    monkeypatch.setattr(
        sheets.settings, "GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}'
    )
    monkeypatch.setattr(sheets.settings, "GOOGLE_SHEET_ID", "sheet-123")
    monkeypatch.setattr(sheets, "_access_token", lambda: "fake-token")

    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return httpx.Response(200, json={})

    monkeypatch.setattr(sheets.httpx, "AsyncClient", FakeAsyncClient)

    await sheets.append_event_lead(
        {"lead_id": 3, "status": "new"},
        "573007778899",
        {
            "event_type": "matrimonio",
            "date": "2026-12-01",
            "guests": 80,
            "budget": 5000000,
            "contact_name": "Juan",
        },
    )

    assert "Eventos" in captured["url"]
    assert captured["json"]["values"] == [
        [3, "573007778899", "matrimonio", "2026-12-01", 80, 5000000, "Juan"]
    ]


async def test_append_order_token_failure_is_logged_not_raised(monkeypatch):
    monkeypatch.setattr(
        sheets.settings, "GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}'
    )
    monkeypatch.setattr(sheets.settings, "GOOGLE_SHEET_ID", "sheet-123")

    def _raise():
        raise RuntimeError("invalid credentials")

    monkeypatch.setattr(sheets, "_access_token", _raise)

    # Must not raise.
    await sheets.append_order(
        {"order_id": 1, "total_cop": 10000, "status": "pending"}, "573001234567"
    )


async def test_append_order_http_failure_is_logged_not_raised(monkeypatch):
    monkeypatch.setattr(
        sheets.settings, "GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}'
    )
    monkeypatch.setattr(sheets.settings, "GOOGLE_SHEET_ID", "sheet-123")
    monkeypatch.setattr(sheets, "_access_token", lambda: "fake-token")

    class FailingAsyncClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, headers=None, json=None):
            return httpx.Response(500, text="server error")

    monkeypatch.setattr(sheets.httpx, "AsyncClient", FailingAsyncClient)

    # response.raise_for_status() raises on 500; must still not propagate.
    await sheets.append_order(
        {"order_id": 1, "total_cop": 10000, "status": "pending"}, "573001234567"
    )
