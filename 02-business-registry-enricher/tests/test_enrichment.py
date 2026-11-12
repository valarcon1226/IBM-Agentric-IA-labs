import asyncio

import pytest

from app import cache, enrichment
from app.registries import companies_house
from app.registries.exceptions import RegistryError, RegistryNotFoundError


def _success_data() -> dict:
    return {
        "company_name": "DEFAULT LIMITED",
        "status": "active",
        "incorporation_date": None,
        "raw_data": {"company_status": "active"},
    }


def test_enrich_cache_hit_skips_registry_call(monkeypatch):
    # A cache hit (fresh row) must never reach the registry connector.
    async def fake_read_cache(country, identifier):
        return _success_data()

    calls = []

    async def fake_lookup(identifier):
        calls.append(identifier)
        return _success_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    result = asyncio.run(enrichment.enrich("GB", "00000006"))

    assert result["cached"] is True
    assert calls == []


def test_enrich_cache_miss_calls_registry_and_caches_result(monkeypatch):
    # A miss (no row, or a row older than 30 days — read_cache returns None for both) must
    # call the registry and cache the successful result.
    async def fake_read_cache(country, identifier):
        return None

    upserts = []

    async def fake_upsert(country, identifier, data):
        upserts.append((country, identifier, data))

    calls = []

    async def fake_lookup(identifier):
        calls.append(identifier)
        return _success_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    result = asyncio.run(enrichment.enrich("GB", "00000006"))

    assert result["cached"] is False
    assert calls == ["00000006"]
    assert len(upserts) == 1
    assert upserts[0][2]["company_name"] == "DEFAULT LIMITED"


def test_enrich_force_refresh_skips_cache_read_but_still_caches(monkeypatch):
    async def fake_read_cache(country, identifier):
        raise AssertionError("cache must not be read when force_refresh=True")

    upserts = []

    async def fake_upsert(country, identifier, data):
        upserts.append((country, identifier, data))

    async def fake_lookup(identifier):
        return _success_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    result = asyncio.run(enrichment.enrich("GB", "00000006", force_refresh=True))

    assert result["cached"] is False
    assert len(upserts) == 1


def test_enrich_not_found_is_never_cached(monkeypatch):
    async def fake_read_cache(country, identifier):
        return None

    async def fake_lookup(identifier):
        raise RegistryNotFoundError("company not found")

    upserts = []

    async def fake_upsert(country, identifier, data):
        upserts.append((country, identifier, data))

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    with pytest.raises(enrichment.NotFoundError):
        asyncio.run(enrichment.enrich("GB", "00000006"))

    assert upserts == []


def test_enrich_registry_error_is_never_cached(monkeypatch):
    async def fake_read_cache(country, identifier):
        return None

    async def fake_lookup(identifier):
        raise RegistryError("upstream failure")

    upserts = []

    async def fake_upsert(country, identifier, data):
        upserts.append((country, identifier, data))

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    with pytest.raises(enrichment.UpstreamError):
        asyncio.run(enrichment.enrich("GB", "00000006"))

    assert upserts == []


def test_enrich_cache_read_failure_raises_cache_error(monkeypatch):
    # DECISIONES-02 E8: a DB error on cache read must surface as CacheError, not bubble up
    # as an unhandled exception.
    async def fake_read_cache(country, identifier):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)

    with pytest.raises(enrichment.CacheError):
        asyncio.run(enrichment.enrich("GB", "00000006"))


def test_enrich_cache_upsert_failure_raises_cache_error(monkeypatch):
    async def fake_read_cache(country, identifier):
        return None

    async def fake_upsert(country, identifier, data):
        raise RuntimeError("connection refused")

    async def fake_lookup(identifier):
        return _success_data()

    monkeypatch.setattr(cache, "read_cache", fake_read_cache)
    monkeypatch.setattr(cache, "upsert_cache", fake_upsert)
    monkeypatch.setattr(companies_house, "lookup", fake_lookup)

    with pytest.raises(enrichment.CacheError):
        asyncio.run(enrichment.enrich("GB", "00000006"))
