"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Invoice Processor microservice."""

    database_url: str = "postgresql://user:change_me_db_password@postgres:5432/invoices"
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "change_me_minio_password"
    minio_bucket: str = "invoices-bucket"
    minio_secure: bool = False

    api_bearer_token: str = "change_me_bearer_token"
    max_sync_pages: int = 1
    tesseract_cmd: str = "tesseract"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
