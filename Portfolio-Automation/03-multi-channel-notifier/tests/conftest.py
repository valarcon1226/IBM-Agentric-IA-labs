import os

TEST_ENV = {
    "DATABASE_URL": "postgresql://postgres:test_password@localhost:5432/test",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "API_KEY": "test_api_key",
    "SMTP_SERVER": "localhost",
    "SMTP_PORT": "1025",
    "SMTP_USER": "test_smtp_user",
    "SMTP_PASSWORD": "test_smtp_password",
    "SMTP_FROM": "notifier@example.com",
    "SLACK_WEBHOOK_URL": "http://localhost:9000/slack",
    "DISCORD_WEBHOOK_URL": "http://localhost:9000/discord",
    "TELEGRAM_BOT_TOKEN": "test_telegram_token",
    "TELEGRAM_API_BASE": "http://localhost:9000/telegram",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
