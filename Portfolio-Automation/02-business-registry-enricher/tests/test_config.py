from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_example_env_satisfies_settings(monkeypatch):
    for line in (Path(__file__).resolve().parents[1] / ".env.example").read_text().splitlines():
        key, value = line.split("=", 1)
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    assert settings.API_KEY == "change_me_api_key"
    assert settings.CH_API_KEY == "change_me_ch_api_key"
    assert settings.INSEE_API_KEY == "change_me_insee_api_key"


@pytest.mark.parametrize(
    "missing_var",
    ["DATABASE_URL", "API_KEY", "CH_API_KEY", "INSEE_API_KEY"],
)
def test_missing_required_var_raises(monkeypatch, missing_var):
    env = {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/test",
        "API_KEY": "test_api_key",
        "CH_API_KEY": "test_ch_api_key",
        "INSEE_API_KEY": "test_insee_api_key",
    }
    del env[missing_var]
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing_var, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
