"""Celery app initialization and beat schedule configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "price_monitor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "check-active-products-periodic": {
            "task": "app.workers.tasks.check_all_active_products",
            "schedule": float(settings.CHECK_INTERVAL_MINUTES * 60),
        },
    },
)
