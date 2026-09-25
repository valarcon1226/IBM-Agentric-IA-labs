# T04 — Las tareas Celery guardan su estado real (proyecto 04)

**Objetivo:** reemplazar el `update_job_status` vacío por `jobs_repo.set_status`. Cada tarea
marca `PROCESSING`, y al final `COMPLETED` con la clave del archivo resultado, o `FAILED`
con el error.

**Archivos que puedes tocar:**
- `04-data-cleaning-api/app/services/tasks.py`
- `04-data-cleaning-api/tests/test_tasks.py` (nuevo)

## Antes de empezar

- `T03` en `DONE`. Compuertas → **31 passed**.

## Paso 1 — `app/services/tasks.py` (reemplazo completo)

EXACTO:

```python
import io
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pandas as pd

from app.core.worker import celery_app
from app.models.db import JobStatus

from . import jobs_repo
from .cleaner import clean_dataframe
from .enricher import normalize_phones, validate_emails
from .storage import download_file, upload_file
from .transformer import aggregate_data, melt_data, merge_columns, pivot_data, split_column

logger = logging.getLogger(__name__)

RESULTS_PREFIX = "results"
TRANSFORMS: dict[str, Callable[..., pd.DataFrame]] = {
    "pivot": pivot_data,
    "melt": melt_data,
    "merge": merge_columns,
    "split": split_column,
    "aggregate": aggregate_data,
}


def _load(file_path: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(download_file(file_path)))


def _run(job_id: str, output_name: str, build: Callable[[], pd.DataFrame]) -> None:
    """Run one job: mark PROCESSING, build the result, store it, mark COMPLETED or FAILED."""
    jid = UUID(job_id)
    jobs_repo.set_status(jid, JobStatus.PROCESSING)
    try:
        out = io.BytesIO()
        build().to_csv(out, index=False)
        key = upload_file(out.getvalue(), f"{RESULTS_PREFIX}/{output_name}")
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        jobs_repo.set_status(jid, JobStatus.FAILED, error_message=f"{type(e).__name__}: {e}")
        return
    jobs_repo.set_status(jid, JobStatus.COMPLETED, output_file_path=key)


def _transform(file_path: str, params: dict[str, Any]) -> pd.DataFrame:
    t_type = params.get("type")
    if t_type not in TRANSFORMS:
        raise ValueError(f"Unknown transform: {t_type}")
    return TRANSFORMS[t_type](_load(file_path), **params.get("args", {}))


def _enrich(file_path: str, ops: list[str], cols: dict[str, str]) -> pd.DataFrame:
    df = _load(file_path)
    if "validate_emails" in ops and cols.get("email"):
        df = validate_emails(df, cols["email"])
    if "normalize_phones" in ops and cols.get("phone"):
        df = normalize_phones(df, cols["phone"])
    return df


@celery_app.task
def process_clean_job(job_id: str, file_path: str, options: dict[str, Any]) -> None:
    _run(job_id, f"cleaned_{job_id}.csv", lambda: clean_dataframe(_load(file_path), options))


@celery_app.task
def process_transform_job(job_id: str, file_path: str, params: dict[str, Any]) -> None:
    _run(job_id, f"transformed_{job_id}.csv", lambda: _transform(file_path, params))


@celery_app.task
def process_enrich_job(
    job_id: str, file_path: str, ops: list[str], cols: dict[str, str]
) -> None:
    _run(job_id, f"enriched_{job_id}.csv", lambda: _enrich(file_path, ops, cols))
```

## Paso 2 — `tests/test_tasks.py` (nuevo)

EXACTO:

```python
from uuid import uuid4

from app.models.db import JobStatus
from app.services import jobs_repo, tasks


def _patch(monkeypatch, csv: bytes = b"A\n1\n1\n", fail_upload: bool = False) -> list:
    statuses: list = []
    monkeypatch.setattr(
        jobs_repo, "set_status", lambda jid, status, **kw: statuses.append((status, kw))
    )
    monkeypatch.setattr(tasks, "download_file", lambda key: csv)

    def fake_upload(content, name):
        if fail_upload:
            raise RuntimeError("minio down")
        return name

    monkeypatch.setattr(tasks, "upload_file", fake_upload)
    return statuses


def test_clean_task_marks_completed_with_output_path(monkeypatch):
    statuses = _patch(monkeypatch)
    job_id = str(uuid4())

    tasks.process_clean_job(job_id, "uploads/x.csv", {"remove_duplicates": True})

    assert [s for s, _ in statuses] == [JobStatus.PROCESSING, JobStatus.COMPLETED]
    assert statuses[-1][1]["output_file_path"] == f"results/cleaned_{job_id}.csv"


def test_clean_task_marks_failed_on_error(monkeypatch):
    statuses = _patch(monkeypatch, fail_upload=True)

    tasks.process_clean_job(str(uuid4()), "uploads/x.csv", {})

    assert [s for s, _ in statuses] == [JobStatus.PROCESSING, JobStatus.FAILED]
    assert "RuntimeError" in statuses[-1][1]["error_message"]


def test_transform_task_rejects_unknown_operation(monkeypatch):
    statuses = _patch(monkeypatch)

    tasks.process_transform_job(str(uuid4()), "uploads/x.csv", {"type": "nope", "args": {}})

    assert [s for s, _ in statuses] == [JobStatus.PROCESSING, JobStatus.FAILED]
    assert "Unknown transform" in statuses[-1][1]["error_message"]
```

## Verificación

1. Compuertas → **34 passed**, ruff y mypy limpios.
2. `Select-String -Path app -Recurse -Pattern "def update_job_status"` → **sin coincidencias**.

## Terminado cuando

Ambas verificaciones pasan. Reporta y marca `T04` como `DONE`.
