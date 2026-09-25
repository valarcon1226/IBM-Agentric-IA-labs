"""Configuration settings for the FastAPI Gateway."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables.

    Shared by the API and the Celery worker/beat. Only the API requires DATABASE_URL and a JWT
    secret (see ``require_api_settings``), so the workers can start with a smaller environment.
    """

    APP_NAME: str = "Portfolio Automation Gateway"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    JWT_SECRET: str | None = None
    JWT_SECRET_FILE: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _load_jwt_secret_file(self) -> "Settings":
        if not self.JWT_SECRET and self.JWT_SECRET_FILE:
            self.JWT_SECRET = Path(self.JWT_SECRET_FILE).read_text(encoding="utf-8").strip()
        return self

    @property
    def get_celery_broker_url(self) -> str:
        """Returns the celery broker URL, falling back to REDIS_URL if not set."""
        return self.CELERY_BROKER_URL or self.REDIS_URL


def require_api_settings(s: Settings) -> None:
    """Fail fast if the API is started without the settings it cannot run without."""
    missing = [
        name
        for name, value in (("DATABASE_URL", s.DATABASE_URL), ("JWT_SECRET", s.JWT_SECRET))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required settings: {', '.join(missing)} (JWT_SECRET_FILE also works)"
        )


settings = Settings()
