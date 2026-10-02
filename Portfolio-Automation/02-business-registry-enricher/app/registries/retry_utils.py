from collections.abc import Awaitable, Callable

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential


class RetryableRegistryError(Exception):
    """Internal: marks a registry response/error as retryable (429, 5xx, network, SOAP fault)."""


async def call_with_retries[T](func: Callable[[], Awaitable[T]], *, wait_seconds: float) -> T:
    """Run ``func`` with tenacity retries on `RetryableRegistryError`/network errors.

    Up to 5 attempts, exponential backoff. ``wait_seconds=0`` (used by tests) makes every
    wait zero instead of actually sleeping between attempts.
    """
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=wait_seconds, min=wait_seconds),
        reraise=True,
    ):
        with attempt:
            return await func()
    raise AssertionError("unreachable: AsyncRetrying always returns or raises")


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RetryableRegistryError):
        return True
    return isinstance(exc, httpx.TransportError)
