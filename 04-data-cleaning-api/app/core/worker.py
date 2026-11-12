from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "data_cleaning_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.tasks"],  # Un-comment or change when tasks are implemented
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.services"])
