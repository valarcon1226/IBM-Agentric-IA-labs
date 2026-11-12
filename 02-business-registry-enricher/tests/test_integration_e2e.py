"""Integration and E2E tests against the real docker-compose stack.

These tests talk to the actual API container (http://localhost:8002) and the real Postgres
(localhost:5434) started by ``docker compose``. They read connection settings from ``E2E_*``
environment variables, falling back to the values documented in ``.env.example``, and skip
cleanly (instead of failing) when the stack is not reachable so the unit suite still runs
without Docker.

DECISIONES-02 E9: the E2E flow does not call any real registry. It inserts a fresh row
directly into ``company_cache``, asserts the enrich endpoints serve it with ``cached: true``
and the README section 5 shape, then deletes the row. The ``cached: false`` path (a real
registry call) is covered by ``tests/test_enrich_api.py`` with mocked connectors.
"""

import json
import os
from datetime import date

import asyncpg
import httpx
import pytest

pytestmark = pytest.mark.integration

## NOTE: dedicated E2E_* names are used (instead of the bare DATABASE_URL/API_KEY/etc. names)
## because tests/conftest.py sets process-wide fallback values for those bare names to satisfy
## app.config.Settings() for the *unit* suite; reusing them here would silently point this test
## at the unit-test fallback instead of the .env.example value the real stack started with.
API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://localhost:8002")
API_KEY = os.environ.get("E2E_API_KEY", "change_me_api_key")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

POSTGRES_HOST = os.environ.get("E2E_POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("E2E_POSTGRES_PORT", "5434"))
POSTGRES_USER = os.environ.get("E2E_POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("E2E_POSTGRES_PASSWORD", "change_me_postgres_password")
POSTGRES_DB = os.environ.get("E2E_POSTGRES_DB", "enricher_db")

GB_IDENTIFIER = "00000006"
FR_IDENTIFIER = "552081317"

_UPSERT_SQL = (
    "INSERT INTO company_cache "
    "(country_code, company_identifier, company_name, status, incorporation_date, raw_data, "
    "last_updated) "
    "VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW()) "
    "ON CONFLICT (country_code, company_identifier) DO UPDATE SET "
    "company_name = EXCLUDED.company_name, "
    "status = EXCLUDED.status, "
    "incorporation_date = EXCLUDED.incorporation_date, "
    "raw_data = EXCLUDED.raw_data, "
    "last_updated = NOW()"
)
_DELETE_SQL = "DELETE FROM company_cache WHERE country_code = $1 AND company_identifier = $2"


async def _pg_connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
    )


async def _seed_cache_row(
    country: str, identifier: str, name: str, status: str, incorporation_date: date, raw: dict
) -> None:
    connection = await _pg_connect()
    try:
        await connection.execute(
            _UPSERT_SQL, country, identifier, name, status, incorporation_date, json.dumps(raw)
        )
    finally:
        await connection.close()


async def _delete_cache_row(country: str, identifier: str) -> None:
    connection = await _pg_connect()
    try:
        await connection.execute(_DELETE_SQL, country, identifier)
    finally:
        await connection.close()


@pytest.fixture(scope="module")
def stack() -> str:
    try:
        httpx.get(f"{API_BASE_URL}/health", timeout=2).raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Docker stack not reachable at {API_BASE_URL}: {exc}")
    return API_BASE_URL


def test_health_endpoint_reports_healthy(stack: str) -> None:
    response = httpx.get(f"{stack}/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_single_enrich_requires_bearer_token(stack: str) -> None:
    response = httpx.get(f"{stack}/api/v1/enrich/GB/{GB_IDENTIFIER}", timeout=5)
    assert response.status_code == 401


@pytest.mark.e2e
def test_single_enrich_gb_served_from_cache(stack: str) -> None:
    import asyncio

    asyncio.run(
        _seed_cache_row(
            "GB", GB_IDENTIFIER, "E2E TEST LIMITED", "active", date(2000, 1, 1), {"source": "e2e"}
        )
    )
    try:
        response = httpx.get(
            f"{stack}/api/v1/enrich/GB/{GB_IDENTIFIER}", headers=HEADERS, timeout=5
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "country": "GB",
            "identifier": GB_IDENTIFIER,
            "company_name": "E2E TEST LIMITED",
            "status": "active",
            "incorporation_date": "2000-01-01",
            "raw_data": {"source": "e2e"},
            "cached": True,
        }
    finally:
        asyncio.run(_delete_cache_row("GB", GB_IDENTIFIER))


@pytest.mark.e2e
def test_single_enrich_fr_served_from_cache(stack: str) -> None:
    import asyncio

    asyncio.run(
        _seed_cache_row(
            "FR",
            FR_IDENTIFIER,
            "SOCIETE AIR FRANCE E2E",
            "active",
            date(1933, 1, 1),
            {"source": "e2e"},
        )
    )
    try:
        response = httpx.get(
            f"{stack}/api/v1/enrich/FR/{FR_IDENTIFIER}", headers=HEADERS, timeout=5
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "country": "FR",
            "identifier": FR_IDENTIFIER,
            "company_name": "SOCIETE AIR FRANCE E2E",
            "status": "active",
            "incorporation_date": "1933-01-01",
            "raw_data": {"source": "e2e"},
            "cached": True,
        }
    finally:
        asyncio.run(_delete_cache_row("FR", FR_IDENTIFIER))


@pytest.mark.e2e
def test_batch_enrich_gb_and_fr_served_from_cache(stack: str) -> None:
    import asyncio

    asyncio.run(
        _seed_cache_row(
            "GB", GB_IDENTIFIER, "E2E TEST LIMITED", "active", date(2000, 1, 1), {"source": "e2e"}
        )
    )
    asyncio.run(
        _seed_cache_row(
            "FR",
            FR_IDENTIFIER,
            "SOCIETE AIR FRANCE E2E",
            "active",
            date(1933, 1, 1),
            {"source": "e2e"},
        )
    )
    try:
        response = httpx.post(
            f"{stack}/api/v1/enrich",
            headers=HEADERS,
            json={
                "companies": [
                    {"country": "GB", "identifier": GB_IDENTIFIER},
                    {"country": "FR", "identifier": FR_IDENTIFIER},
                ]
            },
            timeout=5,
        )
        assert response.status_code == 200
        results = {r["identifier"]: r for r in response.json()["results"]}
        assert results[GB_IDENTIFIER]["company_name"] == "E2E TEST LIMITED"
        assert results[GB_IDENTIFIER]["cached"] is True
        assert results[FR_IDENTIFIER]["company_name"] == "SOCIETE AIR FRANCE E2E"
        assert results[FR_IDENTIFIER]["cached"] is True
    finally:
        asyncio.run(_delete_cache_row("GB", GB_IDENTIFIER))
        asyncio.run(_delete_cache_row("FR", FR_IDENTIFIER))
