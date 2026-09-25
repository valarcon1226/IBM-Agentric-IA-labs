"""
Configuration settings for the FastAPI Gateway.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""
    APP_NAME: str = "Portfolio Automation Gateway"
    APP_VERSION: str = "1.0.0"
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: Optional[str] = None
    JWT_SECRET: str = "insecure-default-secret-change-in-production"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    @property
    def get_celery_broker_url(self) -> str:
        """Returns the celery broker URL, falling back to REDIS_URL if not set."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

settings = Settings()
