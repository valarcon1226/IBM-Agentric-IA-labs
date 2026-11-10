"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure test environment settings
TEST_ENV = {
    "API_TOKEN": "test_api_token",
    "DATABASE_URL": "postgresql+asyncpg://postgres:change_me_postgres_password@localhost:5432/pricemonitor_test",
    "SYNC_DATABASE_URL": "postgresql+psycopg://postgres:change_me_postgres_password@localhost:5432/pricemonitor_test",
    "REDIS_URL": "redis://localhost:6379/1",
    "WEBHOOK_ALERT_URL": "http://localhost:8080/alerts",
    "SCRAPER_USER_AGENT": "PriceMonitorBot/1.0 (+https://example.com/bot)",
    "SCRAPER_MIN_INTERVAL_SECONDS": "0.01",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)

from app.api.main import app  # noqa: E402


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ.get('API_TOKEN', 'test_api_token')}"}
