from pathlib import Path

from app.core.config import Settings
from tests.conftest import TEST_ENV

ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"


def test_env_example_satisfies_required_settings(monkeypatch):
    for key in TEST_ENV:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=ENV_EXAMPLE)  # type: ignore[call-arg]

    assert settings.MINIO_BUCKET
    assert settings.API_KEY
