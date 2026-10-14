import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+psycopg2://user:password@db:5432/scheduler"
    REDIS_URL: str = "redis://redis:6379/0"

    ALERT_WEBHOOK_URL: str | None = "http://webhook-sink:8080/"
    ALERT_WEBHOOK_TOKEN: str | None = None
    FAILURE_ALERT_THRESHOLD: int = 3

    ALLOW_PRIVATE_TARGETS: bool = False
    JOBS_DIR: str = "jobs"
    EXECUTION_TIMEOUT_SECONDS: int = 30
    MAX_OUTPUT_BYTES: int = 100_000

    MAX_RETRIES: int = 3
    BASE_BACKOFF_SECONDS: int = 5

    API_URL: str = "http://api:8000"
    # Bearer token for every /api/v1 route: the API can run scripts, so it is never open.
    API_KEY: str = "change_me_api_key"

    @property
    def jobs_path(self) -> Path:
        p = Path(self.JOBS_DIR)
        if not p.is_absolute():
            # If relative, resolve relative to current working dir or project root
            p = Path(os.getcwd()) / p
        return p.resolve()


settings = Settings()
