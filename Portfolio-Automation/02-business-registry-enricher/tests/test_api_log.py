import asyncio
import logging

from app.registries import api_log


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple] = []

    async def execute(self, statement, params):
        self.executed.append((statement, params))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def begin(self):
        return self._connection


def test_log_api_call_inserts_a_row_on_success(monkeypatch):
    connection = _FakeConnection()
    monkeypatch.setattr(api_log, "get_engine", lambda: _FakeEngine(connection))

    asyncio.run(
        api_log.log_api_call(
            registry_name="companies_house",
            endpoint="https://api.company-information.service.gov.uk/company/00000006",
            company_identifier="00000006",
            response_code=200,
            response_time_ms=42,
            error_message=None,
        )
    )

    assert len(connection.executed) == 1
    params = connection.executed[0][1]
    assert params["registry_name"] == "companies_house"
    assert params["response_code"] == 200
    assert params["error_message"] is None


def test_log_api_call_inserts_a_row_on_failure():
    connection = _FakeConnection()

    import app.registries.api_log as api_log_module

    original_get_engine = api_log_module.get_engine
    api_log_module.get_engine = lambda: _FakeEngine(connection)
    try:
        asyncio.run(
            api_log.log_api_call(
                registry_name="insee",
                endpoint="https://api.insee.fr/api-sirene/3.11/siren/552081317",
                company_identifier="552081317",
                response_code=503,
                response_time_ms=10,
                error_message="INSEE returned unexpected status 503",
            )
        )
    finally:
        api_log_module.get_engine = original_get_engine

    assert len(connection.executed) == 1
    params = connection.executed[0][1]
    assert params["response_code"] == 503
    assert params["error_message"] == "INSEE returned unexpected status 503"


def test_log_write_failure_is_logged_and_not_raised(monkeypatch, caplog):
    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("db unavailable")

    monkeypatch.setattr(api_log, "get_engine", lambda: _BrokenEngine())

    with caplog.at_level(logging.ERROR):
        asyncio.run(
            api_log.log_api_call(
                registry_name="companies_house",
                endpoint="https://api.company-information.service.gov.uk/company/00000006",
                company_identifier="00000006",
                response_code=200,
                response_time_ms=5,
                error_message=None,
            )
        )

    assert any("Failed to write api_logs row" in record.message for record in caplog.records)
