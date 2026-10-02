import asyncio
from datetime import date

import httpx
import pytest

from app.registries import api_log, companies_house
from app.registries.exceptions import RegistryError, RegistryNotFoundError


def _patch_client(monkeypatch, handler):
    def _build_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(companies_house, "_build_client", _build_client)


def _patch_log_spy(monkeypatch):
    calls = []

    async def _fake_log(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(companies_house, "log_api_call", _fake_log)
    return calls


def test_lookup_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/company/00000006"
        return httpx.Response(
            200,
            json={
                "company_name": "DEFAULT LIMITED",
                "company_status": "Active",
                "date_of_creation": "1856-11-20",
                "type": "ltd",
            },
        )

    _patch_client(monkeypatch, handler)
    log_calls = _patch_log_spy(monkeypatch)

    result = asyncio.run(companies_house.lookup("00000006", wait_seconds=0))

    assert result["company_name"] == "DEFAULT LIMITED"
    assert result["status"] == "active"
    assert result["incorporation_date"] == date(1856, 11, 20)
    assert result["raw_data"]["type"] == "ltd"
    assert len(log_calls) == 1
    assert log_calls[0]["response_code"] == 200
    assert log_calls[0]["error_message"] is None
    assert log_calls[0]["company_identifier"] == "00000006"


def test_lookup_not_found_is_not_retried(monkeypatch):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"errors": [{"error": "not-found"}]})

    _patch_client(monkeypatch, handler)
    log_calls = _patch_log_spy(monkeypatch)

    with pytest.raises(RegistryNotFoundError):
        asyncio.run(companies_house.lookup("00000099", wait_seconds=0))

    assert attempts == 1
    assert log_calls[0]["response_code"] == 404
    assert log_calls[0]["error_message"] is not None


def test_lookup_retries_on_429_then_succeeds(monkeypatch):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json={
                "company_name": "DEFAULT LIMITED",
                "company_status": "active",
                "date_of_creation": "1856-11-20",
            },
        )

    _patch_client(monkeypatch, handler)
    _patch_log_spy(monkeypatch)

    result = asyncio.run(companies_house.lookup("00000006", wait_seconds=0))

    assert attempts == 2
    assert result["status"] == "active"


def test_lookup_fails_after_five_attempts_on_5xx(monkeypatch):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": "upstream down"})

    _patch_client(monkeypatch, handler)
    log_calls = _patch_log_spy(monkeypatch)

    with pytest.raises(RegistryError):
        asyncio.run(companies_house.lookup("00000006", wait_seconds=0))

    assert attempts == 5
    assert log_calls[0]["error_message"] is not None


def test_log_write_failure_does_not_break_lookup(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"company_name": "DEFAULT LIMITED", "company_status": "active"},
        )

    _patch_client(monkeypatch, handler)

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("db unavailable")

    monkeypatch.setattr(api_log, "get_engine", lambda: _BrokenEngine())

    result = asyncio.run(companies_house.lookup("00000006", wait_seconds=0))

    assert result["company_name"] == "DEFAULT LIMITED"
