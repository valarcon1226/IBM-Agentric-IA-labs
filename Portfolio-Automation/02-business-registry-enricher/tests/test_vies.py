import asyncio

import pytest
import zeep.exceptions

from app.registries import api_log, vies
from app.registries.exceptions import RegistryError


class _FakeVatResponse:
    def __init__(self, *, valid: bool, name: str | None = None) -> None:
        self.valid = valid
        self.name = name
        self.countryCode = "FR"
        self.vatNumber = "552081317"


class _FakeService:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls = 0

    def checkVat(self, countryCode: str, vatNumber: str):
        self.calls += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeClient:
    def __init__(self, responses: list) -> None:
        self.service = _FakeService(responses)


def _patch_client(monkeypatch, responses: list) -> _FakeClient:
    fake_client = _FakeClient(responses)
    monkeypatch.setattr(vies, "_build_client", lambda: fake_client)
    return fake_client


def _patch_log_spy(monkeypatch):
    calls = []

    async def _fake_log(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(vies, "log_api_call", _fake_log)
    return calls


def test_lookup_valid_vat(monkeypatch):
    fake_client = _patch_client(
        monkeypatch, [_FakeVatResponse(valid=True, name="SOCIETE AIR FRANCE")]
    )
    log_calls = _patch_log_spy(monkeypatch)

    result = asyncio.run(vies.lookup("FR", "552081317", wait_seconds=0))

    assert result["status"] == "valid"
    assert result["company_name"] == "SOCIETE AIR FRANCE"
    assert result["incorporation_date"] is None
    assert fake_client.service.calls == 1
    assert log_calls[0]["response_code"] == 200
    assert log_calls[0]["company_identifier"] == "FR552081317"


def test_lookup_invalid_vat_is_a_successful_response(monkeypatch):
    # DECISIONES-02 E7: VIES "invalid" is a valid response, not a not-found error.
    _patch_client(monkeypatch, [_FakeVatResponse(valid=False)])
    _patch_log_spy(monkeypatch)

    result = asyncio.run(vies.lookup("FR", "000000000", wait_seconds=0))

    assert result["status"] == "invalid"


def test_lookup_retries_on_service_fault_then_succeeds(monkeypatch):
    fake_client = _patch_client(
        monkeypatch,
        [
            zeep.exceptions.Fault("MS_UNAVAILABLE"),
            _FakeVatResponse(valid=True, name="SOCIETE AIR FRANCE"),
        ],
    )
    log_calls = _patch_log_spy(monkeypatch)

    result = asyncio.run(vies.lookup("FR", "552081317", wait_seconds=0))

    assert fake_client.service.calls == 2
    assert result["status"] == "valid"
    assert log_calls[0]["error_message"] is None


def test_lookup_fails_after_five_attempts_on_persistent_fault(monkeypatch):
    fake_client = _patch_client(monkeypatch, [zeep.exceptions.Fault("MS_UNAVAILABLE")] * 5)
    log_calls = _patch_log_spy(monkeypatch)

    with pytest.raises(RegistryError):
        asyncio.run(vies.lookup("FR", "552081317", wait_seconds=0))

    assert fake_client.service.calls == 5
    assert log_calls[0]["error_message"] is not None


def test_log_write_failure_does_not_break_lookup(monkeypatch):
    _patch_client(monkeypatch, [_FakeVatResponse(valid=True, name="SOCIETE AIR FRANCE")])

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("db unavailable")

    monkeypatch.setattr(api_log, "get_engine", lambda: _BrokenEngine())

    result = asyncio.run(vies.lookup("FR", "552081317", wait_seconds=0))

    assert result["company_name"] == "SOCIETE AIR FRANCE"


@pytest.mark.live
def test_lookup_against_vies_test_service():
    # Optional: hits the real VIES checkVatTestService with the official "always valid" number.
    # Excluded by default (see pyproject.toml addopts); run explicitly with `-m live`.
    original_wsdl = vies.WSDL_URL
    vies.WSDL_URL = "https://ec.europa.eu/taxation_customs/vies/checkVatTestService.wsdl"
    try:
        result = asyncio.run(vies.lookup("DE", "100", wait_seconds=1))
        assert result["status"] == "valid"
    finally:
        vies.WSDL_URL = original_wsdl
