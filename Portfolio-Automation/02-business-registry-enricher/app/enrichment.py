from typing import Any

from app import cache
from app.registries import companies_house, insee, vies
from app.registries.exceptions import RegistryError, RegistryNotFoundError


class NotFoundError(Exception):
    """The registry confirmed the identifier does not exist."""


class UpstreamError(Exception):
    """The registry call failed after exhausting retries."""


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
    `NotFoundError` if the registry confirms the identifier doesn't exist, or `UpstreamError`
    if the registry fails after retries. `force_refresh=True` skips the cache read but still
    updates the cache on a successful lookup.
    """
    if not force_refresh:
        cached = await cache.read_cache(country, identifier)
        if cached is not None:
            return {**cached, "cached": True}

    try:
        data = await _call_registry(country, identifier)
    except RegistryNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except RegistryError as exc:
        raise UpstreamError(str(exc)) from exc

    await cache.upsert_cache(country, identifier, data)
    return {**data, "cached": False}
