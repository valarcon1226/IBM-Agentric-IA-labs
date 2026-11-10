from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    # LLM client (DECISIONES-13 W6, used from batch B onward but configured here per W3).
    LLM_BASE_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str
    # Tests/local demos only (DECISIONES-13 W6): routes the agent to the scripted fake LLM in
    # `app.fake_llm` instead of a real OpenAI-compatible endpoint. Never set true in production.
    LLM_FAKE: bool = False

    # WhatsApp Cloud API — required only when WHATSAPP_ENABLED=true.
    WHATSAPP_ENABLED: bool = False
    WHATSAPP_TOKEN: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_APP_SECRET: str | None = None
    WHATSAPP_VERIFY_TOKEN: str | None = None
    GRAPH_API_VERSION: str = "v23.0"
    GRAPH_API_BASE: str = "https://graph.facebook.com"

    # Comma-separated phone numbers of staff who can use the human-handover commands (W7).
    STAFF_WA_IDS: str = ""

    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = None
    GOOGLE_SHEET_ID: str | None = None

    # Reservation reminders (W9): template name for the day-before reminder (outside WhatsApp's
    # 24h customer-service window, an approved template is required). "hello_world" is the
    # default approved template on a fresh WhatsApp Business test account.
    REMINDER_TEMPLATE: str = "hello_world"

    # Dev mode (W5): exposes POST /dev/chat without needing a real Meta account.
    DEV_MODE: bool = False
    DEV_API_KEY: str | None = None
    ADMIN_API_KEY: str | None = None
    WEB_CORS_ORIGINS: str = "*"

    @property
    def web_cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.WEB_CORS_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def staff_wa_id_list(self) -> list[str]:
        return [wa_id.strip() for wa_id in self.STAFF_WA_IDS.split(",") if wa_id.strip()]

    @model_validator(mode="after")
    def _check_conditional_requirements(self) -> "Settings":
        if self.WHATSAPP_ENABLED:
            required = (
                "WHATSAPP_TOKEN",
                "WHATSAPP_PHONE_NUMBER_ID",
                "WHATSAPP_APP_SECRET",
                "WHATSAPP_VERIFY_TOKEN",
            )
            missing = [name for name in required if not getattr(self, name)]
            if missing:
                raise ValueError(
                    "Missing required settings when WHATSAPP_ENABLED=true: " + ", ".join(missing)
                )
        if self.DEV_MODE and not self.DEV_API_KEY:
            raise ValueError("DEV_API_KEY is required when DEV_MODE=true")
        return self


settings = Settings()
