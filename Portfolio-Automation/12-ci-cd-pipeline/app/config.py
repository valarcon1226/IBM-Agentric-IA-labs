from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "12-ci-cd-pipeline-api"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql://appuser:change_me_db_password@localhost:5432/deployments_db"
    DEBUG: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
