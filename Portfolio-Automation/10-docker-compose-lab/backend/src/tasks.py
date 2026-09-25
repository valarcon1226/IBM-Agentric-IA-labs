"""
Celery tasks for the application.
"""
import logging
from .celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="health_check_task")
def health_check() -> str:
    """
    A simple health check task that returns 'OK'.
    Used to verify Celery workers are processing tasks.
    """
    logger.info("Health check task executed.")
    return "OK"
