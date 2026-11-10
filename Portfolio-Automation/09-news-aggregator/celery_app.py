"""Celery worker and beat scheduler configuration."""

import logging

from celery import Celery
from celery.schedules import crontab

from api.config import settings

logger = logging.getLogger(__name__)

celery = Celery(
    "news_aggregator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    beat_schedule={
        "periodic-news-ingestion": {
            "task": "celery_app.ingest_sources_task",
            "schedule": 900.0,  # every 15 minutes
        },
        "daily-intelligence-digest": {
            "task": "celery_app.generate_digest_task",
            "schedule": crontab(hour=8, minute=0),  # Daily at 8:00 UTC
            "kwargs": {"target_audience": "TEAM_DIGEST"},
        },
    },
)


@celery.task(name="celery_app.ingest_sources_task")
def ingest_sources_task():
    """Background task to run news ingestion pipeline."""
    from ingestion.pipeline import run_ingestion_pipeline

    logger.info("Starting scheduled ingestion pipeline...")
    results = run_ingestion_pipeline()
    logger.info(f"Scheduled ingestion completed: {results}")
    return results


@celery.task(name="celery_app.generate_digest_task")
def generate_digest_task(target_audience: str = "TEAM_DIGEST", recipient_email: str | None = None):
    """Background task to generate and deliver daily digest."""
    from ingestion.pipeline import generate_and_dispatch_digest

    logger.info(f"Starting scheduled digest generation for {target_audience}...")
    digest = generate_and_dispatch_digest(
        target_audience=target_audience, recipient_email=recipient_email
    )
    logger.info(f"Digest generated with ID: {digest.get('id')}, status: {digest.get('status')}")
    return {"digest_id": str(digest.get("id")), "status": digest.get("status")}
