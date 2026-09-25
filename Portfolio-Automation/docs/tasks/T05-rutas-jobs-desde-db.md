# T05 — `/jobs` lee Postgres; se eliminan los mocks y los modelos duplicados (proyecto 04)

**Objetivo:** `GET /api/v1/jobs/{job_id}` y `GET /api/v1/jobs/{job_id}/result` usan
`jobs_repo`. Se borra `MOCK_JOBS`. `app/models/domain.py` queda solo con `JobResponse`
(las otras clases no las importa nadie y no coinciden con las rutas).

**Archivos que puedes tocar:**
- `04-data-cleaning-api/app/api/routes/jobs.py`
- `04-data-cleaning-api/app/models/domain.py`
- `04-data-cleaning-api/tests/test_api.py`

## Antes de empezar

- `T04` en `DONE`. Compuertas → **34 passed**.
- `Select-String -Path app, tests -Recurse -Pattern "models.domain|from app.models import domain"`
  → **sin coincidencias**. Si hay alguna, detente y repórtala.

## Paso 1 — `app/models/domain.py` (reemplazo completo)

EXACTO:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    """Public view of a persisted job."""

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: str
    operation_type: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

## Paso 2 — `app/api/routes/jobs.py` (reemplazo completo)

EXACTO:

```python
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db import JobStatus
from app.models.domain import JobResponse
from app.services import jobs_repo
from app.services.storage import generate_presigned_url

logger = logging.getLogger(__name__)
router = APIRouter()

DOWNLOAD_URL_TTL_SECONDS = 3600


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: UUID, db: Session = Depends(get_db)):
    job = jobs_repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: UUID, db: Session = Depends(get_db)):
    job = jobs_repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.COMPLETED or not job.output_file_path:
        raise HTTPException(400, "Job not completed")
    try:
        url = generate_presigned_url(job.output_file_path, expires=DOWNLOAD_URL_TTL_SECONDS)
    except Exception as e:
        logger.exception("Could not presign result for job %s", job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"job_id": str(job_id), "download_url": url, "expires_in": DOWNLOAD_URL_TTL_SECONDS}
```

## Paso 3 — `tests/test_api.py`

3a. Agrega a los imports (ruff los ordena):

```python
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.api.routes import jobs
```

Si ya hay una línea `from app.api.routes import clean, enrich, transform, upload`, agrega
`jobs` a esa misma línea en vez de crear otra.

3b. **Borra** la función completa `test_unknown_job_result_returns_404` (la reemplaza la
versión con UUID de abajo).

3c. Al final del archivo agrega. EXACTO:

```python


def _job(**overrides):
    base = {
        "job_id": uuid4(),
        "status": "COMPLETED",
        "operation_type": "clean",
        "error_message": None,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
        "output_file_path": "results/cleaned.csv",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def fake_db():
    app.dependency_overrides[get_db] = lambda: object()
    yield
    app.dependency_overrides.clear()


def test_get_job_returns_persisted_state(monkeypatch, fake_db):
    job = _job(status="PROCESSING")
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: job)

    res = client.get(f"/api/v1/jobs/{job.job_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "PROCESSING"
    assert body["job_id"] == str(job.job_id)
    assert "output_file_path" not in body


def test_unknown_job_returns_404(monkeypatch, fake_db):
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: None)
    assert client.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    assert client.get(f"/api/v1/jobs/{uuid4()}/result").status_code == 404


def test_invalid_job_id_returns_422(fake_db):
    assert client.get("/api/v1/jobs/not-a-uuid").status_code == 422


def test_job_result_not_completed_returns_400(monkeypatch, fake_db):
    job = _job(status="PROCESSING", output_file_path=None)
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: job)
    assert client.get(f"/api/v1/jobs/{job.job_id}/result").status_code == 400


def test_job_result_returns_presigned_url(monkeypatch, fake_db):
    job = _job()
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: job)
    monkeypatch.setattr(
        jobs, "generate_presigned_url", lambda key, expires: f"https://minio.local/{key}"
    )

    res = client.get(f"/api/v1/jobs/{job.job_id}/result")

    assert res.status_code == 200
    assert res.json() == {
        "job_id": str(job.job_id),
        "download_url": "https://minio.local/results/cleaned.csv",
        "expires_in": 3600,
    }
```

## Verificación

1. Compuertas → **38 passed**, ruff y mypy limpios.
2. `Select-String -Path app -Recurse -Pattern "MOCK_JOBS|CleanOptions|SchemaCreate"` → **sin coincidencias**.

## Terminado cuando

Ambas verificaciones pasan. Reporta y marca `T05` como `DONE`.
