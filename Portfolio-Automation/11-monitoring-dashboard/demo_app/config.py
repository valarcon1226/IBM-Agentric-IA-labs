from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "demo-app"
    environment: str = "production"
    log_file_path: str = "/var/log/demo-app/app.log"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/demo_db"


settings = Settings()
