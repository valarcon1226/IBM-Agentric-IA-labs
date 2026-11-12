import asyncio

import pytest
from aiolimiter import AsyncLimiter


async def _assert_blocks_once_drained(limiter: AsyncLimiter, capacity: int) -> None:
    for _ in range(capacity):
        await limiter.acquire()

    assert limiter.has_capacity() is False

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(limiter.acquire(), timeout=0.2)


def test_companies_house_limiter_blocks_after_600_in_window():
    # Same config as app.registries.companies_house._limiter (README section 6 / E5): a fresh
    # instance is used here so this test cannot exhaust the module-level production limiter.
    limiter = AsyncLimiter(600, 300)
    asyncio.run(_assert_blocks_once_drained(limiter, 600))


def test_insee_limiter_blocks_after_30_in_window():
    # Same config as app.registries.insee._limiter (README section 6 / E5).
    limiter = AsyncLimiter(30, 60)
    asyncio.run(_assert_blocks_once_drained(limiter, 30))
