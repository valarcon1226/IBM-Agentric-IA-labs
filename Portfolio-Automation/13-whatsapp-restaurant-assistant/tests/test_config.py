import pytest
from pydantic import ValidationError

from app.config import Settings

BASE_ENV = {
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/test",
    "LLM_BASE_URL": "http://localhost:9000/v1",
    "LLM_API_KEY": "test_llm_api_key",
    "LLM_MODEL": "test-model",
}

DEV_MODE_VARS = ["DEV_MODE", "DEV_API_KEY"]
WHATSAPP_VARS = [
    "WHATSAPP_ENABLED",
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_APP_SECRET",
    "WHATSAPP_VERIFY_TOKEN",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """These tests build Settings from scratch: strip whatever conftest.py put in os.environ."""
    for key in {
        *BASE_ENV,
        *DEV_MODE_VARS,
        *WHATSAPP_VARS,
        "STAFF_WA_IDS",
        "GRAPH_API_VERSION",
        "GRAPH_API_BASE",
    }:
        monkeypatch.delenv(key, raising=False)
    for key, value in BASE_ENV.items():
        monkeypatch.setenv(key, value)


def test_minimal_settings_load():
    settings = Settings(_env_file=None)
    assert settings.WHATSAPP_ENABLED is False
    assert settings.DEV_MODE is False
    assert settings.GRAPH_API_VERSION == "v23.0"
    assert settings.GRAPH_API_BASE == "https://graph.facebook.com"


def test_missing_required_field_raises(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_whatsapp_enabled_requires_credentials(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ENABLED", "true")
    with pytest.raises(ValidationError, match="WHATSAPP_ENABLED=true"):
        Settings(_env_file=None)


def test_whatsapp_enabled_with_all_credentials_ok(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_TOKEN", "t")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "p")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "v")
    settings = Settings(_env_file=None)
    assert settings.WHATSAPP_ENABLED is True


def test_dev_mode_requires_dev_api_key(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    with pytest.raises(ValidationError, match="DEV_API_KEY"):
        Settings(_env_file=None)


def test_dev_mode_with_key_ok(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("DEV_API_KEY", "k")
    settings = Settings(_env_file=None)
    assert settings.DEV_MODE is True


def test_staff_wa_id_list_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("STAFF_WA_IDS", "573001111111, 573002222222 ,,")
    settings = Settings(_env_file=None)
    assert settings.staff_wa_id_list == ["573001111111", "573002222222"]


def test_staff_wa_id_list_empty_by_default():
    settings = Settings(_env_file=None)
    assert settings.staff_wa_id_list == []
