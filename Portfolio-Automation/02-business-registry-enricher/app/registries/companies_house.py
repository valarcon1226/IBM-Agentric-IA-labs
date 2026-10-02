import time
from datetime import date
from typing import Any

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.registries.api_log import log_api_call
from app.registries.exceptions import RegistryError, RegistryNotFoundError
from app.registries.retry_utils import RetryableRegistryError, call_with_retries

REGISTRY_NAME = "companies_house"
BASE_URL = "https://api.company-information.service.gov.uk"

# 600 requests / 5 minutes, per README section 6 / DECISIONES-02 E5.
_limiter = AsyncLimiter(600, 300)


def _build_client() -> httpx.AsyncClient:
    # Companies House uses HTTP Basic Auth with the API key as username, empty password.
    return httpx.AsyncClient(auth=(settings.CH_API_KEY, ""))


async def _fetch(identifier: str) -> httpx.Response:
    # Each attempt (retries included) takes a limiter slot, so retries count against the quota.
    async with _limiter, _build_client() as client:
        response = await client.get(f"{BASE_URL}/company/{identifier}")
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableRegistryError(f"Companies House returned HTTP {response.status_code}")
    return response


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    status = data.get("company_status")
    incorporation_date_raw = data.get("date_of_creation")
    return {
        "company_name": data.get("company_name"),
        "status": status.lower() if isinstance(status, str) else None,
        "incorporation_date": (
            date.fromisoformat(incorporation_date_raw) if incorporation_date_raw else None
        ),
        "raw_data": data,
    }


async def lookup(identifier: str, *, wait_seconds: float = 1.0) -> dict[str, Any]:
    """Look up a GB company by its Companies House company number.

    Raises `RegistryNotFoundError` on HTTP 404 (not retried) and `RegistryError` if the
    registry keeps failing (429/5xx/network error) after retries.
    """
    endpoint = f"{BASE_URL}/company/{identifier}"
    started = time.monotonic()
    response_code: int | None = None
    error_message: str | None = None
    try:
        response = await _call_registry(identifier, wait_seconds)
        response_code = response.status_code
        if response.status_code == 404:
            raise RegistryNotFoundError(f"Companies House: company {identifier} not found")
        if response.status_code != 200:
            raise RegistryError(
                f"Companies House returned unexpected status {response.status_code}"
            )
        return _normalize(response.json())
    except (RegistryNotFoundError, RegistryError) as exc:
        error_message = str(exc)
        raise
    except Exception as exc:
        error_message = str(exc)
        raise RegistryError(f"Companies House lookup failed for {identifier}") from exc
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
