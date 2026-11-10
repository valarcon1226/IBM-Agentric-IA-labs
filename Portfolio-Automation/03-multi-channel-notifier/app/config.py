from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    CELERY_BROKER_URL: str
    API_KEY: str

    # Email (SMTP) — all four required together for the channel to be configured.
    SMTP_SERVER: str | None = None
    SMTP_PORT: int | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None

    # Slack / Discord webhooks.
    SLACK_WEBHOOK_URL: str | None = None
    DISCORD_WEBHOOK_URL: str | None = None

    # Telegram.
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_API_BASE: str = "https://api.telegram.org"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def configured_channels(self) -> set[str]:
        channels: set[str] = set()
        if self.SMTP_SERVER and self.SMTP_PORT and self.SMTP_USER and self.SMTP_PASSWORD:
            channels.add("email")
        if self.SLACK_WEBHOOK_URL:
            channels.add("slack")
        if self.DISCORD_WEBHOOK_URL:
            channels.add("discord")
        if self.TELEGRAM_BOT_TOKEN:
            channels.add("telegram")
        return channels


settings = Settings()
