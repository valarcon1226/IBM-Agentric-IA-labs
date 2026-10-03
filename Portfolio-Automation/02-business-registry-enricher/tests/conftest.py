import os

import pytest
from aiolimiter import AsyncLimiter

TEST_ENV = {
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/test",
    "API_KEY": "test_api_key",
    "CH_API_KEY": "test_ch_api_key",
    "INSEE_API_KEY": "test_insee_api_key",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)

from app.registries import companies_house, insee  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_registry_limiters(monkeypatch):
    # Each test runs its own event loop (asyncio.run), but companies_house._limiter and
    # insee._limiter are created once at import time: reusing them across loops triggers
    # "AsyncLimiter instance is being re-used across loops". A fresh instance per test (same
    # rate as production) avoids the warning without touching production code.
    monkeypatch.setattr(companies_house, "_limiter", AsyncLimiter(600, 300))
    monkeypatch.setattr(insee, "_limiter", AsyncLimiter(30, 60))
