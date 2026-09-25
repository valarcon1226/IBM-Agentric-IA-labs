# T02 — Repositorio de jobs `jobs_repo.py` (proyecto 04)

**Objetivo:** funciones únicas para crear, leer y cambiar el estado de un job en Postgres.
Nadie más escribe en la tabla `jobs`. Esta tarea **solo crea el módulo**; T03–T05 lo usan y
T06 lo prueba contra un Postgres real.

**Archivos que puedes tocar:** `04-data-cleaning-api/app/services/jobs_repo.py` (nuevo).

## Antes de empezar

- `docs/tasks/README.md` muestra `T01` en `DONE`.
- Compuertas → **29 passed**.

## Paso 1 — crear `app/services/jobs_repo.py`

EXACTO:

```python
"""Single write path for the `jobs` table."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.db import JobModel, JobStatus

MAX_ERROR_LENGTH = 500


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
```

## Verificación

1. Compuertas → **29 passed** (sin cambio: este módulo se prueba en T06), ruff y mypy limpios.
2. `Select-String -Path app\services\jobs_repo.py -Pattern "def create_job|def get_job|def set_status"`
   → exactamente 3 coincidencias.

## Terminado cuando

Ambas verificaciones pasan. Reporta y marca `T02` como `DONE`.
