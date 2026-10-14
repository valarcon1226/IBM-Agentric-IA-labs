"""Configuration settings using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql://news_user:change_me_postgres_password@localhost:5432/newsdb"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "intelligence@news-aggregator.local"
    DEFAULT_DIGEST_EMAIL: str = "briefing@empresa-ficticia.com"

    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:8080/v1"
    LLM_API_KEY: str = "none"
    LLM_MODEL: str = "llama3:8b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    SIMILARITY_THRESHOLD: float = 0.15

    API_BEARER_TOKEN: str = "change_me_api_bearer_token"
    # Feed and article URLs come from API users: internal addresses are refused unless a demo needs them.
    ALLOW_PRIVATE_TARGETS: bool = False
    API_PORT: int = 8009


settings = Settings()
