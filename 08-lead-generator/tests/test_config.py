from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("API_KEY", "secret")
    settings = Settings()
    assert settings.DATABASE_URL == "postgresql://u:p@host:5432/db"
    assert settings.API_KEY == "secret"
    assert settings.GOOGLE_PLACES_API_KEY is None
    assert settings.SCRAPER_RATE_LIMIT_PER_SECOND == 1.0
    assert settings.FUZZY_MATCH_THRESHOLD == 85


def test_settings_require_database_url_and_api_key(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    try:
        Settings(_env_file=None)
        raise AssertionError("expected missing required settings to fail validation")
    except Exception:
        pass
