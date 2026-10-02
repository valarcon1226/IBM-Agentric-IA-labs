import asyncio
from datetime import date

from app import cache


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConnection:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple] = []

    async def execute(self, statement, params):
        self.executed.append((str(statement), params))
        return _FakeResult(self.rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def connect(self):
        return self._connection

    def begin(self):
        return self._connection


def test_read_cache_returns_none_on_miss(monkeypatch):
    connection = _FakeConnection(rows=[])
    monkeypatch.setattr(cache, "get_engine", lambda: _FakeEngine(connection))

    result = asyncio.run(cache.read_cache("GB", "00000006"))

    assert result is None
    statement, params = connection.executed[0]
    assert "last_updated > NOW() - INTERVAL '30 days'" in statement
    assert params == {"country_code": "GB", "identifier": "00000006"}


def test_read_cache_returns_row_on_hit(monkeypatch):
    row = {
        "company_name": "DEFAULT LIMITED",
        "status": "active",
        "incorporation_date": date(1856, 11, 20),
        "raw_data": {"company_status": "active"},
    }
    connection = _FakeConnection(rows=[row])
    monkeypatch.setattr(cache, "get_engine", lambda: _FakeEngine(connection))

    result = asyncio.run(cache.read_cache("GB", "00000006"))

    assert result == row


def test_upsert_cache_runs_insert_on_conflict(monkeypatch):
    connection = _FakeConnection()
    monkeypatch.setattr(cache, "get_engine", lambda: _FakeEngine(connection))

    asyncio.run(
        cache.upsert_cache(
            "FR",
            "552081317",
            {
                "company_name": "SOCIETE AIR FRANCE",
                "status": "active",
                "incorporation_date": date(1933, 1, 1),
                "raw_data": {"siren": "552081317"},
            },
        )
    )

    statement, params = connection.executed[0]
    assert "INSERT INTO company_cache" in statement
    assert "ON CONFLICT (country_code, company_identifier) DO UPDATE" in statement
    assert "last_updated = NOW()" in statement
    assert params["country_code"] == "FR"
    assert params["identifier"] == "552081317"
    assert params["company_name"] == "SOCIETE AIR FRANCE"
    assert params["raw_data"] == '{"siren": "552081317"}'
