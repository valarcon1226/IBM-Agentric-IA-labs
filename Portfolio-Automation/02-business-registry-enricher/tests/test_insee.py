import asyncio
from datetime import date

import httpx
import pytest

from app.registries import api_log, insee
from app.registries.exceptions import RegistryError, RegistryNotFoundError


def _patch_client(monkeypatch, handler):
    def _build_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(insee, "_build_client", _build_client)


def _patch_log_spy(monkeypatch):
    calls = []

    async def _fake_log(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(insee, "log_api_call", _fake_log)
    return calls


def _sirene_payload(etat: str = "A") -> dict:
    return {
        "uniteLegale": {
            "siren": "552081317",
            "dateCreationUniteLegale": "1933-01-01",
            "periodesUniteLegale": [
                {
                    "dateFin": None,
                    "denominationUniteLegale": "SOCIETE AIR FRANCE",
                    "etatAdministratifUniteLegale": etat,
                }
            ],
        }
    }


def test_lookup_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api-sirene/3.11/siren/552081317"
        return httpx.Response(200, json=_sirene_payload())

    _patch_client(monkeypatch, handler)
    log_calls = _patch_log_spy(monkeypatch)

    result = asyncio.run(insee.lookup("552081317", wait_seconds=0))

    assert result["company_name"] == "SOCIETE AIR FRANCE"
    assert result["status"] == "active"
    assert result["incorporation_date"] == date(1933, 1, 1)
    assert len(log_calls) == 1
    assert log_calls[0]["response_code"] == 200


def test_lookup_falls_back_to_individual_entrepreneur_name(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "uniteLegale": {
                "siren": "123456789",
                "dateCreationUniteLegale": "2010-05-01",
                "periodesUniteLegale": [
                    {
                        "dateFin": None,
                        "denominationUniteLegale": None,
                        "nomUniteLegale": "DUPONT",
                        "prenom1UniteLegale": "JEAN",
                        "etatAdministratifUniteLegale": "A",
                    }
                ],
            }
        }
        return httpx.Response(200, json=payload)

    _patch_client(monkeypatch, handler)
    _patch_log_spy(monkeypatch)

    result = asyncio.run(insee.lookup("123456789", wait_seconds=0))

    assert result["company_name"] == "JEAN DUPONT"
    assert result["status"] == "active"


def test_lookup_ceased_status(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_sirene_payload(etat="C"))

    _patch_client(monkeypatch, handler)
    _patch_log_spy(monkeypatch)

    result = asyncio.run(insee.lookup("552081317", wait_seconds=0))

    assert result["status"] == "ceased"


def test_lookup_not_found_is_not_retried(monkeypatch):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"header": {"message": "no results"}})

    _patch_client(monkeypatch, handler)
    log_calls = _patch_log_spy(monkeypatch)

    with pytest.raises(RegistryNotFoundError):
        asyncio.run(insee.lookup("000000000", wait_seconds=0))

    assert attempts == 1
    assert log_calls[0]["response_code"] == 404


def test_lookup_retries_on_429_then_succeeds(monkeypatch):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_sirene_payload())

    _patch_client(monkeypatch, handler)
    _patch_log_spy(monkeypatch)

    result = asyncio.run(insee.lookup("552081317", wait_seconds=0))

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
        asyncio.run(insee.lookup("552081317", wait_seconds=0))

    assert attempts == 5
    assert log_calls[0]["error_message"] is not None


def test_log_write_failure_does_not_break_lookup(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_sirene_payload())

    _patch_client(monkeypatch, handler)

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("db unavailable")

    monkeypatch.setattr(api_log, "get_engine", lambda: _BrokenEngine())

    result = asyncio.run(insee.lookup("552081317", wait_seconds=0))

    assert result["company_name"] == "SOCIETE AIR FRANCE"
