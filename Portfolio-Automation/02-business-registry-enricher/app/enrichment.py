import logging
from typing import Any

from app import cache
from app.registries import companies_house, insee, vies
from app.registries.exceptions import RegistryError, RegistryNotFoundError

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """The registry confirmed the identifier does not exist."""


class UpstreamError(Exception):
    """The registry call failed after exhausting retries."""


class CacheError(Exception):
    """The cache read/upsert failed (e.g. database unavailable)."""


async def _call_registry(country: str, identifier: str) -> dict[str, Any]:
    # DECISIONES-02 E4: GB -> Companies House, FR -> INSEE, any other EU member state -> VIES.
    if country == "GB":
        return await companies_house.lookup(identifier)
    if country == "FR":
        return await insee.lookup(identifier)
    return await vies.lookup(country, identifier)


async def enrich(country: str, identifier: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Cache-first lookup for one (country, identifier) pair (DECISIONES-02 E7/E8).

    Returns a dict with company_name/status/incorporation_date/raw_data/cached. Raises
    `NotFoundError` if the registry confirms the identifier doesn't exist, `UpstreamError`
    if the registry fails after retries, or `CacheError` if the database read/upsert fails
    (DECISIONES-02 E8: a cache/DB error for one item must not abort the whole batch).
    `force_refresh=True` skips the cache read but still updates the cache on a successful
    lookup.
    """
    if not force_refresh:
        try:
            cached = await cache.read_cache(country, identifier)
        except Exception as exc:
            logger.exception("Cache read failed for %s/%s", country, identifier)
            raise CacheError(str(exc)) from exc
        if cached is not None:
            return {**cached, "cached": True}

    try:
        data = await _call_registry(country, identifier)
    except RegistryNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except RegistryError as exc:
        raise UpstreamError(str(exc)) from exc

    try:
        await cache.upsert_cache(country, identifier, data)
    except Exception as exc:
        logger.exception("Cache upsert failed for %s/%s", country, identifier)
        raise CacheError(str(exc)) from exc
    return {**data, "cached": False}
