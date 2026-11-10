import logging
from datetime import UTC, datetime

import httpx
from celery import Celery

from app.core.config import settings
from app.executors.base import ExecutionResult
from app.executors.http_executor import execute_http
from app.executors.python_executor import execute_python
from app.executors.shell_executor import execute_shell
from app.models.database import SessionLocal, Task, TaskDependency, TaskRun

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

celery_app = Celery("scheduler_engine", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    beat_dburi=db_url,
    beat_max_loop_interval=5,
    timezone="UTC",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    enable_utc=True,
)


def send_failure_alert(task_id: str, task_name: str, failures: int, error_msg: str) -> None:
    if not settings.ALERT_WEBHOOK_URL:
        return
    try:
        alert_payload = {
            "template_name": "slack_alert",
            "channels": ["slack"],
            "priority": "high",
            "recipients": {},
            "payload": {
                "severity": "CRITICAL",
                "message": (
                    f"Task '{task_name}' ({task_id}) failed {failures} "
                    f"consecutive times. Error: {error_msg}"
                ),
                "system": "scheduler-engine",
            },
            "event": "task_consecutive_failures",
            "task_id": str(task_id),
            "task_name": task_name,
            "consecutive_failures": failures,
            "error": error_msg,
        }
        headers = {"Content-Type": "application/json"}
        if settings.ALERT_WEBHOOK_TOKEN:
            headers["x-api-key"] = settings.ALERT_WEBHOOK_TOKEN

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(settings.ALERT_WEBHOOK_URL, json=alert_payload, headers=headers)
            logger.info(f"Webhook alert sent for task {task_id}, status code: {resp.status_code}")
    except Exception as exc:
        logger.error(f"Failed to send webhook alert for task {task_id}: {exc}")


@celery_app.task(bind=True, name="app.core.celery_app.run_scheduled_task", max_retries=10)
def run_scheduled_task(self, task_id: str, is_manual: bool = False):
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            logger.warning(f"Task {task_id} not found.")
            return {"status": "NOT_FOUND"}

        # Beat should only run active tasks
        if not task.is_active and not is_manual:
            logger.info(f"Task {task_id} is paused/inactive. Skipping scheduled run.")
            return {"status": "PAUSED"}

        # Check dependencies
        dependencies = db.query(TaskDependency).filter(TaskDependency.task_id == task_id).all()
        for dep in dependencies:
            last_run = (
                db.query(TaskRun)
                # Only finished runs count; a run still in progress is not a failure.
                .filter(
                    TaskRun.task_id == dep.depends_on_task_id,
                    TaskRun.status.in_(("SUCCESS", "FAILED")),
                )
                .order_by(TaskRun.started_at.desc())
                .first()
            )
            if not last_run or last_run.status != "SUCCESS":
                dep_status = last_run.status if last_run else "NO_RUNS"
                msg = (
                    f"Skipped: dependency task {dep.depends_on_task_id} "
                    f"status was '{dep_status}' (expected SUCCESS)."
                )
                skipped_run = TaskRun(
                    task_id=task.task_id,
                    status="SKIPPED",
                    stdout=msg,
                    stderr="",
                    exit_code=0,
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                    duration_ms=0,
                )
                db.add(skipped_run)
                db.commit()
                logger.info(f"Task {task_id} skipped due to dependency {dep.depends_on_task_id}.")
                return {"status": "SKIPPED", "reason": msg}

        # Create RUNNING record
        run = TaskRun(
            task_id=task.task_id,
            status="RUNNING",
            started_at=datetime.now(UTC),
        )
        db.add(run)
        task.last_run_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)

        # Execute according to task_type
        task_type = (task.task_type or "").upper()
        if task_type == "HTTP":
            result = execute_http(task.payload)
        elif task_type == "SHELL":
            result = execute_shell(task.payload)
        elif task_type == "PYTHON":
            result = execute_python(task.payload)
        else:
            result = ExecutionResult(
                status="FAILED",
                stdout="",
                stderr=f"Unsupported task type: {task_type}",
                exit_code=-1,
                duration_ms=0,
            )

        if result.status == "SUCCESS":
            run.status = "SUCCESS"
            run.stdout = result.stdout
            run.stderr = result.stderr
            run.exit_code = result.exit_code
            run.finished_at = datetime.now(UTC)
            run.duration_ms = result.duration_ms
            task.consecutive_failures = 0
            db.commit()
            return {"status": "SUCCESS", "run_id": run.run_id}
        else:
            # Handle retries
            current_retry = self.request.retries
            max_retries = task.max_retries if task.max_retries is not None else settings.MAX_RETRIES
            if current_retry < max_retries:
                backoff_base = (
                    task.retry_backoff
                    if task.retry_backoff is not None
                    else settings.BASE_BACKOFF_SECONDS
                )
                countdown = backoff_base * (2**current_retry)
                run.status = "RETRYING"
                run.stdout = result.stdout
                run.stderr = (
                    f"Attempt {current_retry + 1}/{max_retries + 1} failed: {result.stderr}. "
                    f"Retrying in {countdown}s."
                )
                run.exit_code = result.exit_code
                run.finished_at = datetime.now(UTC)
                run.duration_ms = result.duration_ms
                db.commit()
                logger.info(
                    f"Task {task_id} failed on retry {current_retry + 1}, retrying in {countdown}s."
                )
                raise self.retry(countdown=countdown, exc=Exception(result.stderr))
            else:
                # Retries exhausted -> mark FAILED
                run.status = "FAILED"
                run.stdout = result.stdout
                run.stderr = result.stderr
                run.exit_code = result.exit_code
                run.finished_at = datetime.now(UTC)
                run.duration_ms = result.duration_ms
                task.consecutive_failures += 1
                db.commit()

                # Alerting if consecutive failures threshold reached
                if task.consecutive_failures >= settings.FAILURE_ALERT_THRESHOLD:
                    send_failure_alert(
                        task_id=task.task_id,
                        task_name=task.name,
                        failures=task.consecutive_failures,
                        error_msg=result.stderr,
                    )

                return {"status": "FAILED", "run_id": run.run_id}
