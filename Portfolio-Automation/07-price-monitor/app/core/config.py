"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "change_me_postgres_password"
    POSTGRES_DB: str = "pricemonitor"
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:change_me_postgres_password@postgres:5432/pricemonitor"
    )
    SYNC_DATABASE_URL: str = (
        "postgresql+psycopg://postgres:change_me_postgres_password@postgres:5432/pricemonitor"
    )
    REDIS_URL: str = "redis://redis:6379/0"

    API_TOKEN: str = "change_me_api_token"
    WEBHOOK_ALERT_URL: str = "http://webhook-sink:8080/alerts"
    CHECK_INTERVAL_MINUTES: int = 5

    SCRAPER_USER_AGENT: str = "PriceMonitorBot/1.0 (+https://example.com/bot)"
    SCRAPER_MIN_INTERVAL_SECONDS: float = 1.0
    # Product URLs come from API users; block internal addresses (SSRF) unless a demo needs them.
    ALLOW_PRIVATE_TARGETS: bool = False

    # Fallback/rewrites for local vs container demo-store URL resolution
    DEMO_STORE_INTERNAL_URL: str = "http://demo-store"
    DEMO_STORE_EXTERNAL_PORT: int = 8087
    IN_DOCKER: bool = False
    API_BASE_URL: str = "http://127.0.0.1:8007"


settings = Settings()
