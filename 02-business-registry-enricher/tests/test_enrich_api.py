from fastapi.testclient import TestClient

from app import cache, main
from app.registries import companies_house, insee
from app.registries.exceptions import RegistryError, RegistryNotFoundError

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer test_api_key"}


def _gb_data() -> dict:
    return {
        "company_name": "DEFAULT LIMITED",
        "status": "active",
        "incorporation_date": None,
        "raw_data": {"company_status": "active"},
    }


def test_single_enrich_first_call_not_cached_then_cached(monkeypatch):
    store: dict[tuple[str, str], dict] = {}

    async def fake_read_cache(country, identifier):
        return store.get((country, identifier))

    async def fake_upsert(country, identifier, data):
        store[(country, identifier)] = data

    calls = []

    async def fake_lookup(identifier):
        calls.append(identifier)
        return _gb_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    first = client.get("/api/v1/enrich/GB/00000006", headers=AUTH)
    assert first.status_code == 200
    assert first.json()["cached"] is False

    second = client.get("/api/v1/enrich/GB/00000006", headers=AUTH)
    assert second.status_code == 200
    assert second.json()["cached"] is True

    assert calls == ["00000006"]


def test_single_enrich_force_refresh_skips_cache_read(monkeypatch):
    async def fake_read_cache(country, identifier):
        raise AssertionError("cache must not be read when force_refresh=true")

    upserts = []

    async def fake_upsert(country, identifier, data):
        upserts.append((country, identifier))

    async def fake_lookup(identifier):
        return _gb_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    response = client.get("/api/v1/enrich/GB/00000009?force_refresh=true", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["cached"] is False
    assert upserts == [("GB", "00000009")]


def test_single_enrich_not_found_returns_404(monkeypatch):
    async def fake_read_cache(country, identifier):
        return None

    async def fake_lookup(identifier):
        raise RegistryNotFoundError("gone")

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    response = client.get("/api/v1/enrich/GB/00000007", headers=AUTH)

    assert response.status_code == 404


def test_single_enrich_registry_failure_returns_502(monkeypatch):
    async def fake_read_cache(country, identifier):
        return None

    async def fake_lookup(identifier):
        raise RegistryError("down")

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    response = client.get("/api/v1/enrich/GB/00000008", headers=AUTH)

    assert response.status_code == 502


def test_single_enrich_cache_failure_returns_503(monkeypatch):
    async def fake_read_cache(country, identifier):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)

    response = client.get("/api/v1/enrich/GB/00000010", headers=AUTH)

    assert response.status_code == 503


def test_batch_enrich_one_failing_item(monkeypatch):
    async def fake_read_cache(country, identifier):
        return None

    async def fake_upsert(country, identifier, data):
        return None

    async def fake_ch_lookup(identifier):
        return _gb_data()

    async def fake_insee_lookup(identifier):
        raise RegistryNotFoundError("not found")

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_ch_lookup)
    monkeypatch.setattr(insee, "lookup", fake_insee_lookup)

    response = client.post(
        "/api/v1/enrich",
        headers=AUTH,
        json={
            "companies": [
                {"country": "GB", "identifier": "00000006"},
                {"country": "FR", "identifier": "552081317"},
            ]
        },
    )

    assert response.status_code == 200
    results = {r["identifier"]: r for r in response.json()["results"]}
    assert results["00000006"]["company_name"] == "DEFAULT LIMITED"
    assert results["00000006"]["cached"] is False
    assert results["552081317"]["status"] == "not_found"
    assert results["552081317"]["company_name"] is None
    assert results["552081317"]["error"] == "Company not found"


def test_batch_enrich_one_item_with_cache_error_does_not_abort_batch(monkeypatch):
    # DECISIONES-02 E8: a cache/DB failure for one item must become that item's error result,
    # not a 500 for the whole batch.
    async def fake_read_cache(country, identifier):
        if identifier == "00000006":
            return None
        raise RuntimeError("connection refused")

    async def fake_upsert(country, identifier, data):
        return None

    async def fake_ch_lookup(identifier):
        return _gb_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_ch_lookup)

    response = client.post(
        "/api/v1/enrich",
        headers=AUTH,
        json={
            "companies": [
                {"country": "GB", "identifier": "00000006"},
                {"country": "GB", "identifier": "00000007"},
            ]
        },
    )

    assert response.status_code == 200
    results = {r["identifier"]: r for r in response.json()["results"]}
    assert results["00000006"]["company_name"] == "DEFAULT LIMITED"
    assert results["00000007"]["status"] == "error"
    assert results["00000007"]["error"] == "Cache temporarily unavailable"


def test_batch_enrich_requires_bearer_token():
    response = client.post(
        "/api/v1/enrich",
        json={"companies": [{"country": "GB", "identifier": "00000006"}]},
    )
    assert response.status_code == 401


def test_single_enrich_requires_bearer_token():
    response = client.get("/api/v1/enrich/GB/00000006")
    assert response.status_code == 401


def test_single_enrich_rejects_invalid_identifier():
    response = client.get("/api/v1/enrich/GB/bad", headers=AUTH)
    assert response.status_code == 422


def test_batch_enrich_rejects_invalid_country():
    response = client.post(
        "/api/v1/enrich",
        headers=AUTH,
        json={"companies": [{"country": "US", "identifier": "12345678"}]},
    )
    assert response.status_code == 422
