"""
Celery application configuration.
"""
from celery import Celery
from .config import settings

# Initialize Celery
celery_app = Celery(
    "portfolio_tasks",
    broker=settings.get_celery_broker_url,
    backend=settings.REDIS_URL
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Placeholder for beat schedule
    beat_schedule={},
)

# Autodiscover tasks from the src module
celery_app.autodiscover_tasks(["src"])
