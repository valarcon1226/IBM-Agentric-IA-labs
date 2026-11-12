from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def _env_from_example() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (Path(__file__).resolve().parents[1] / ".env.example").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


def test_example_env_satisfies_settings(monkeypatch):
    for key, value in _env_from_example().items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    assert settings.API_KEY == "change_me_api_key"
    assert settings.CELERY_BROKER_URL == "redis://redis:6379/0"
    assert settings.DATABASE_URL.startswith("postgresql://postgres:")


@pytest.mark.parametrize("missing_var", ["DATABASE_URL", "CELERY_BROKER_URL", "API_KEY"])
def test_missing_required_var_raises(monkeypatch, missing_var):
    env = {
        "DATABASE_URL": "postgresql://postgres:test@localhost:5432/test",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "API_KEY": "test_api_key",
    }
    del env[missing_var]
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing_var, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_optional_channel_vars_default_to_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:test@localhost:5432/test")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("API_KEY", "test_api_key")
    for var in (
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SLACK_WEBHOOK_URL",
        "DISCORD_WEBHOOK_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_API_BASE",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.configured_channels == set()
    assert settings.TELEGRAM_API_BASE == "https://api.telegram.org"


def test_configured_channels_reflects_present_vars(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:test@localhost:5432/test")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("API_KEY", "test_api_key")
    monkeypatch.setenv("SMTP_SERVER", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "http://localhost/slack")
    for var in ("DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.configured_channels == {"email", "slack"}
