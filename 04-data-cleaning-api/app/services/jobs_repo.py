"""Single write path for the `jobs` table."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.db import JobModel, JobStatus

MAX_ERROR_LENGTH = 500

logger = logging.getLogger(__name__)


def create_job(
    db: Session, job_id: UUID, operation_type: str, input_file_path: str | None
) -> JobModel:
    job = JobModel(
        job_id=job_id,
        operation_type=operation_type,
        input_file_path=input_file_path,
        status=JobStatus.PENDING.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: UUID) -> JobModel | None:
    return db.get(JobModel, job_id)


def set_status(
    job_id: UUID,
    status: JobStatus,
    *,
    output_file_path: str | None = None,
    error_message: str | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Update a job's status in its own session (safe to call from Celery workers)."""
    with session_factory() as db:
        job = db.get(JobModel, job_id)
        if job is None:
            raise LookupError(f"Job {job_id} not found")
        now = datetime.now(UTC)
        job.status = status.value
        if status is JobStatus.PROCESSING:
            job.started_at = now
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = now
        if output_file_path is not None:
            job.output_file_path = output_file_path
        if error_message is not None:
            job.error_message = error_message[:MAX_ERROR_LENGTH]
        db.commit()


def mark_enqueue_failed(job_id: UUID) -> None:
    """Best effort: record that the job never reached the queue."""
    try:
        set_status(job_id, JobStatus.FAILED, error_message="Could not enqueue job")
    except Exception:
        logger.exception("Could not mark job %s as failed", job_id)
