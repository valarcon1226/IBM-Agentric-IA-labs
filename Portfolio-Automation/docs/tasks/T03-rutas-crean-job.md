# T03 — Las rutas que encolan crean el job en Postgres antes de encolar (proyecto 04)

**Objetivo:** `/clean` (rama asíncrona), `/transform` y `/enrich` registran el job como
`PENDING` **antes** de mandarlo a Celery. Si no se puede encolar, el job queda `FAILED`.
La respuesta HTTP no cambia: `{"status": "processing", "job_id": "<uuid>"}`.

**Archivos que puedes tocar:**
- `04-data-cleaning-api/app/services/jobs_repo.py`
- `04-data-cleaning-api/app/api/routes/clean.py`
- `04-data-cleaning-api/app/api/routes/transform.py`
- `04-data-cleaning-api/app/api/routes/enrich.py`
- `04-data-cleaning-api/tests/test_api.py`

## Antes de empezar

- `T02` en `DONE`. Compuertas → **29 passed**.

## Paso 1 — `app/services/jobs_repo.py`

1a. Debajo de `"""Single write path for the `jobs` table."""` y antes de los imports existentes,
agrega `import logging` en el bloque de imports de la biblioteca estándar (ruff ordena; corre
`ruff check --fix` si hace falta).

1b. Debajo de `MAX_ERROR_LENGTH = 500` agrega. EXACTO:

```python
logger = logging.getLogger(__name__)
```

1c. Al final del archivo agrega. EXACTO:

```python


def mark_enqueue_failed(job_id: UUID) -> None:
    """Best effort: record that the job never reached the queue."""
    try:
        set_status(job_id, JobStatus.FAILED, error_message="Could not enqueue job")
    except Exception:
        logger.exception("Could not mark job %s as failed", job_id)
```

## Paso 2 — `app/api/routes/transform.py` (reemplazo completo)

EXACTO:

```python
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import jobs_repo
from app.services.tasks import process_transform_job

logger = logging.getLogger(__name__)
router = APIRouter()


class TransformRequest(BaseModel):
    file_path: str
    operation: str
    params: dict[str, Any]


@router.post("/transform")
def transform_data(request: TransformRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4()
    jobs_repo.create_job(db, job_id, "transform", request.file_path)
    try:
        process_transform_job.delay(
            str(job_id), request.file_path, {"type": request.operation, "args": request.params}
        )
    except Exception as e:
        logger.exception("Could not enqueue transform job %s", job_id)
        jobs_repo.mark_enqueue_failed(job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"status": "processing", "job_id": str(job_id)}
```

## Paso 3 — `app/api/routes/enrich.py` (reemplazo completo)

EXACTO:

```python
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import jobs_repo
from app.services.tasks import process_enrich_job

logger = logging.getLogger(__name__)
router = APIRouter()


class EnrichRequest(BaseModel):
    file_path: str
    operations: list[str]
    target_columns: dict[str, str]


@router.post("/enrich")
def enrich_data(request: EnrichRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4()
    jobs_repo.create_job(db, job_id, "enrich", request.file_path)
    try:
        process_enrich_job.delay(
            str(job_id), request.file_path, request.operations, request.target_columns
        )
    except Exception as e:
        logger.exception("Could not enqueue enrich job %s", job_id)
        jobs_repo.mark_enqueue_failed(job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"status": "processing", "job_id": str(job_id)}
```

## Paso 4 — `app/api/routes/clean.py` (reemplazo completo)

EXACTO:

```python
import io
import json
import logging
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services import jobs_repo
from app.services.cleaner import clean_dataframe
from app.services.storage import upload_file
from app.services.tasks import process_clean_job

logger = logging.getLogger(__name__)
router = APIRouter()
MAX_SYNC_BYTES = settings.MAX_SYNC_SIZE_MB * 1024 * 1024
PARSE_ERRORS = (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError)


@router.post("/clean")
async def clean_data(
    file: UploadFile = File(...),
    options: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        options_dict = json.loads(options)
    except json.JSONDecodeError as e:
        raise HTTPException(400, "Invalid options JSON") from e

    file_bytes = await file.read()
    if len(file_bytes) < MAX_SYNC_BYTES:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except PARSE_ERRORS as e:
            raise HTTPException(400, f"Could not parse file: {type(e).__name__}") from e
        try:
            return {
                "status": "success",
                "data": clean_dataframe(df, options_dict).to_dict(orient="records"),
            }
        except Exception as e:
            logger.exception("Synchronous cleaning failed")
            raise HTTPException(500, "Internal processing error") from e

    job_id = uuid.uuid4()
    try:
        obj_key = upload_file(file_bytes, f"raw_{job_id}_{file.filename}")
    except Exception as e:
        logger.exception("Could not store upload for job %s", job_id)
        raise HTTPException(500, "Internal processing error") from e
    jobs_repo.create_job(db, job_id, "clean", obj_key)
    try:
        process_clean_job.delay(str(job_id), obj_key, options_dict)
    except Exception as e:
        logger.exception("Could not enqueue clean job %s", job_id)
        jobs_repo.mark_enqueue_failed(job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"status": "processing", "job_id": str(job_id)}
```

## Paso 5 — `tests/test_api.py`

5a. Imports: en la línea `from app.services import storage`, cámbiala a
`from app.services import jobs_repo, storage`, y agrega la línea
`from app.models.db import JobStatus` (deja que `ruff check --fix` ordene los imports).

5b. Debajo del fixture `healthy_dependencies` agrega este fixture. EXACTO:

```python
@pytest.fixture
def fake_jobs(monkeypatch):
    """Replace the jobs table with an in-memory call log; no database needed."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        jobs_repo,
        "create_job",
        lambda db, job_id, operation_type, input_file_path: calls.append(
            ("create", str(job_id), operation_type, input_file_path)
        ),
    )
    monkeypatch.setattr(
        jobs_repo,
        "set_status",
        lambda job_id, status, **kwargs: calls.append(("status", str(job_id), status, kwargs)),
    )
    app.dependency_overrides[get_db] = lambda: object()
    yield calls
    app.dependency_overrides.clear()
```

5c. Agrega el parámetro `fake_jobs` a estas **tres** funciones existentes (solo la firma, no
cambies su cuerpo):
- `def test_clean_large_file_is_queued_not_processed_inline(monkeypatch):` →
  `def test_clean_large_file_is_queued_not_processed_inline(monkeypatch, fake_jobs):`
- `def test_transform_accepts_documented_payload(monkeypatch):` → `(monkeypatch, fake_jobs):`
- `def test_enrich_accepts_documented_payload(monkeypatch):` → `(monkeypatch, fake_jobs):`

5d. Al final del archivo agrega. EXACTO:

```python


def test_async_clean_creates_pending_job_before_queueing(monkeypatch, fake_jobs):
    monkeypatch.setattr(clean, "upload_file", lambda content, name: name)
    monkeypatch.setattr(
        clean.process_clean_job, "delay", lambda *args: fake_jobs.append(("delay", *args))
    )
    monkeypatch.setattr(clean, "MAX_SYNC_BYTES", 64)

    res = client.post(
        "/api/v1/clean",
        files={"file": ("big.csv", io.BytesIO(b"A\n" + b"1\n" * 64), "text/csv")},
        data={"options": "{}"},
    )

    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert [c[0] for c in fake_jobs] == ["create", "delay"]
    assert fake_jobs[0][1:3] == (job_id, "clean")
    assert fake_jobs[1][1] == job_id


def test_enqueue_failure_marks_job_failed(monkeypatch, fake_jobs):
    def broker_down(*args):
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(transform.process_transform_job, "delay", broker_down)

    res = client.post("/api/v1/transform", json=README_TRANSFORM_PAYLOAD)

    assert res.status_code == 500
    assert [c[0] for c in fake_jobs] == ["create", "status"]
    assert fake_jobs[1][2] == JobStatus.FAILED
```

## Verificación

1. Compuertas → **31 passed**, ruff y mypy limpios.
2. `Select-String -Path app\api\routes\clean.py, app\api\routes\transform.py, app\api\routes\enrich.py -Pattern "jobs_repo.create_job"`
   → exactamente **3** coincidencias.

## Terminado cuando

Ambas verificaciones pasan. Reporta y marca `T03` como `DONE`.
