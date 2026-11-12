"""Configuración de la aplicación usando Pydantic Settings."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de configuración del servicio."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "cafe_de_origen"

    # Servidor SMTP (Mailpit en desarrollo/compose)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "pedidos@cafedeorigen.co"

    # Secretos para verificación de Webhooks
    WOOCOMMERCE_WEBHOOK_SECRET: str = "change_me_woocommerce_secret"
    SHOPIFY_WEBHOOK_SECRET: str = "change_me_shopify_secret"
    STRIPE_WEBHOOK_SECRET: str = "whsec_change_me_stripe_secret"

    # Credenciales del panel administrativo
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change_me_admin_password"
    SECRET_KEY: str = "change_me_session_secret_key"

    # Notificaciones WhatsApp (Opcional - WhatsApp Cloud API)
    WHATSAPP_API_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None

    # Modo de pruebas / entorno
    TESTING: bool = False


settings = Settings()
