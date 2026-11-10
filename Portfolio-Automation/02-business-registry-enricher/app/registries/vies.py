import asyncio
import time
from functools import cache
from typing import Any

import requests
import zeep.exceptions
import zeep.helpers
from zeep import Client
from zeep.transports import Transport

from app.registries.api_log import log_api_call
from app.registries.exceptions import RegistryError
from app.registries.retry_utils import RetryableRegistryError, call_with_retries

REGISTRY_NAME = "vies"
WSDL_URL = "https://ec.europa.eu/taxation_customs/vies/checkVatService.wsdl"


@cache
def _build_client() -> Client:
    # Cached: building the client downloads and parses the WSDL.
    return Client(WSDL_URL, transport=Transport(timeout=10))


def _check_vat_sync(country_code: str, vat_number: str) -> Any:
    try:
        client = _build_client()
        return client.service.checkVat(countryCode=country_code, vatNumber=vat_number)
    except requests.RequestException as exc:
        # Fetching the WSDL failed (network); retryable like any transport error.
        raise RetryableRegistryError(f"VIES WSDL unavailable: {exc}") from exc
    except zeep.exceptions.Fault as exc:
        # VIES service faults (e.g. MS_UNAVAILABLE, timeouts) are transient; retry them.
        raise RetryableRegistryError(f"VIES service fault: {exc}") from exc
    except zeep.exceptions.TransportError as exc:
        raise RetryableRegistryError(f"VIES transport error: {exc}") from exc


def _normalize(result: Any) -> dict[str, Any]:
    return {
        "company_name": getattr(result, "name", None),
        "status": "valid" if result.valid else "invalid",
        "incorporation_date": None,
        "raw_data": zeep.helpers.serialize_object(result, dict),
    }


async def lookup(
    country_code: str, identifier: str, *, wait_seconds: float = 1.0
) -> dict[str, Any]:
    """Validate an EU VAT number via the VIES `checkVat` SOAP operation.

    Both `valid` and `invalid` are successful responses (DECISIONES-02 E7); only a persistent
    SOAP fault/transport error after retries raises `RegistryError`. zeep is synchronous, so the
    call runs in a worker thread via `asyncio.to_thread`.
    """
    endpoint = f"{WSDL_URL}#checkVat"
    started = time.monotonic()
    response_code: int | None = None
    error_message: str | None = None
    try:
        result = await call_with_retries(
            lambda: asyncio.to_thread(_check_vat_sync, country_code, identifier),
            wait_seconds=wait_seconds,
        )
        response_code = 200
        return _normalize(result)
    except Exception as exc:
        error_message = str(exc)
        raise RegistryError(f"VIES lookup failed for {country_code}{identifier}") from exc
    finally:
        await log_api_call(
            registry_name=REGISTRY_NAME,
            endpoint=endpoint,
            company_identifier=f"{country_code}{identifier}",
            response_code=response_code,
            response_time_ms=int((time.monotonic() - started) * 1000),
            error_message=error_message,
        )
