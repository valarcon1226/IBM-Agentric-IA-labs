from celery import Celery

from app.config import settings

# Redis-only broker (DECISIONES-03 N7): no result backend, results are ignored —
# delivery state lives in `delivery_logs`/`notifications`, written by the tasks themselves.
celery_app = Celery(
    "notifier",
    broker=settings.CELERY_BROKER_URL,
    include=[
        "app.workers.email_task",
        "app.workers.slack_task",
        "app.workers.discord_task",
        "app.workers.telegram_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    # Redis priority support (approximate, N7): 10 buckets, high=0 ... low=9.
    task_queue_max_priority=9,
    task_default_priority=5,
    broker_transport_options={
        "priority_steps": list(range(10)),
        "queue_order_strategy": "priority",
    },
)
