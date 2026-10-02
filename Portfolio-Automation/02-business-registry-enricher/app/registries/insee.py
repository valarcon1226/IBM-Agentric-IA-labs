import time
from datetime import date
from typing import Any

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.registries.api_log import log_api_call
from app.registries.exceptions import RegistryError, RegistryNotFoundError
from app.registries.retry_utils import RetryableRegistryError, call_with_retries

REGISTRY_NAME = "insee"
BASE_URL = "https://api.insee.fr/api-sirene/3.11"

# The old bearer-token portal was replaced by Sirene 3.11 (DECISIONES-02 E5); it authenticates
# with the X-INSEE-Api-Key-Integration header instead.
_HEADER_NAME = "X-INSEE-Api-Key-Integration"

# 30 requests / minute, per README section 6 / DECISIONES-02 E5.
_limiter = AsyncLimiter(30, 60)

_ETAT_TO_STATUS = {"A": "active", "C": "ceased"}


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={_HEADER_NAME: settings.INSEE_API_KEY})


async def _fetch(identifier: str) -> httpx.Response:
    # Each attempt (retries included) takes a limiter slot, so retries count against the quota.
    async with _limiter, _build_client() as client:
        response = await client.get(f"{BASE_URL}/siren/{identifier}")
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableRegistryError(f"INSEE returned HTTP {response.status_code}")
    return response


def _company_name(unite_legale: dict[str, Any], current_period: dict[str, Any]) -> str | None:
    denomination = current_period.get("denominationUniteLegale")
    if denomination:
        return denomination
    # Individual entrepreneurs (personnes physiques) have no denomination; INSEE carries their
    # name as nomUniteLegale/prenom1UniteLegale instead. Prefer the current period's values,
    # falling back to the uniteLegale level in case a given payload doesn't historize them.
    nom = current_period.get("nomUniteLegale") or unite_legale.get("nomUniteLegale")
    if not nom:
        return None
    prenom = current_period.get("prenom1UniteLegale") or unite_legale.get("prenom1UniteLegale")
    return f"{prenom} {nom}" if prenom else nom


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    unite_legale = data.get("uniteLegale", {})
    # denominationUniteLegale/etatAdministratifUniteLegale are historized: the current values
    # live in the first entry of periodesUniteLegale (dateFin == null), not at the top level.
    periods = unite_legale.get("periodesUniteLegale") or [{}]
    current_period = periods[0]
    etat = current_period.get("etatAdministratifUniteLegale")
    incorporation_date_raw = unite_legale.get("dateCreationUniteLegale")
    return {
        "company_name": _company_name(unite_legale, current_period),
        "status": _ETAT_TO_STATUS.get(etat, etat.lower() if isinstance(etat, str) else None),
        "incorporation_date": (
            date.fromisoformat(incorporation_date_raw) if incorporation_date_raw else None
        ),
        "raw_data": data,
    }


async def lookup(identifier: str, *, wait_seconds: float = 1.0) -> dict[str, Any]:
    """Look up a FR company by its SIREN number.

    Raises `RegistryNotFoundError` on HTTP 404 (not retried) and `RegistryError` if the
    registry keeps failing (429/5xx/network error) after retries.
    """
    endpoint = f"{BASE_URL}/siren/{identifier}"
    started = time.monotonic()
    response_code: int | None = None
    error_message: str | None = None
    try:
        response = await _call_registry(identifier, wait_seconds)
        response_code = response.status_code
        if response.status_code == 404:
            raise RegistryNotFoundError(f"INSEE: SIREN {identifier} not found")
        if response.status_code != 200:
            raise RegistryError(f"INSEE returned unexpected status {response.status_code}")
        return _normalize(response.json())
    except (RegistryNotFoundError, RegistryError) as exc:
        error_message = str(exc)
        raise
    except Exception as exc:
        error_message = str(exc)
        raise RegistryError(f"INSEE lookup failed for {identifier}") from exc
    finally:
        await log_api_call(
            registry_name=REGISTRY_NAME,
            endpoint=endpoint,
            company_identifier=identifier,
            response_code=response_code,
            response_time_ms=int((time.monotonic() - started) * 1000),
            error_message=error_message,
        )


async def _call_registry(identifier: str, wait_seconds: float) -> httpx.Response:
    return await call_with_retries(lambda: _fetch(identifier), wait_seconds=wait_seconds)
