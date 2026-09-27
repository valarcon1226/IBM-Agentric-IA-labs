# T06 — Tests de integración contra un Postgres real (proyecto 04)

**Objetivo:** probar `jobs_repo` y la regla `ON DELETE SET NULL` contra Postgres 16 real
(con `testcontainers`), aplicando el mismo `init-db.sql` que usa Docker. Estos tests:
- **no** corren en el `pytest` normal (se excluyen con un marcador);
- corren en CI en un paso aparte, donde **fallan** si no hay Docker (no se saltan en silencio);
- en local se **saltan** con un mensaje claro si Docker Desktop no está encendido.

**Archivos que puedes tocar:**
- `04-data-cleaning-api/requirements-dev.txt`
- `04-data-cleaning-api/pyproject.toml`
- `04-data-cleaning-api/tests/integration/__init__.py` (nuevo, vacío)
- `04-data-cleaning-api/tests/integration/conftest.py` (nuevo)
- `04-data-cleaning-api/tests/integration/test_jobs_repo.py` (nuevo)

## Antes de empezar

- `T05` en `DONE`. Compuertas → **38 passed**.

## Paso 1 — `requirements-dev.txt`

Agrega al final esta línea. EXACTO:

```
testcontainers[postgres]==4.15.0
```

Después: `uv pip install -p .venv\Scripts\python.exe -r requirements-dev.txt`.

## Paso 2 — `pyproject.toml`

Reemplaza el bloque `[tool.pytest.ini_options]` completo por. EXACTO:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -m \"not integration\""
markers = ["integration: needs Docker (real Postgres via testcontainers)"]
```

## Paso 3 — `tests/integration/__init__.py`

Archivo vacío.

## Paso 4 — `tests/integration/conftest.py`

EXACTO:

```python
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

INIT_SQL = Path(__file__).resolve().parents[2] / "init-db.sql"


@pytest.fixture(scope="session")
def pg_engine():
    """Postgres 16 with init-db.sql applied. Skips locally without Docker; fails in CI."""
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as e:
        if os.getenv("REQUIRE_DOCKER") == "1":
            raise
        pytest.skip(f"Docker not available: {e}")
    try:
        engine = create_engine(container.get_connection_url())
        with engine.begin() as conn:
            conn.exec_driver_sql(INIT_SQL.read_text(encoding="utf-8"))
        yield engine
        engine.dispose()
    finally:
        container.stop()


@pytest.fixture
def session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, expire_on_commit=False)
```

## Paso 5 — `tests/integration/test_jobs_repo.py`

EXACTO:

```python
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.db import JobModel, JobStatus, SchemaModel
from app.services import jobs_repo

pytestmark = pytest.mark.integration


def test_job_lifecycle_is_persisted(session_factory):
    job_id = uuid4()
    with session_factory() as db:
        jobs_repo.create_job(db, job_id, "clean", "uploads/x.csv")

    jobs_repo.set_status(job_id, JobStatus.PROCESSING, session_factory=session_factory)
    jobs_repo.set_status(
        job_id,
        JobStatus.COMPLETED,
        output_file_path="results/x.csv",
        session_factory=session_factory,
    )

    with session_factory() as db:
        job = jobs_repo.get_job(db, job_id)
    assert job is not None
    assert job.status == "COMPLETED"
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.output_file_path == "results/x.csv"


def test_deleting_schema_keeps_its_jobs(session_factory):
    job_id = uuid4()
    with session_factory() as db:
        schema = SchemaModel(name=f"tmp-{job_id}", definition={"fields": {}})
        db.add(schema)
        db.commit()
        db.add(JobModel(job_id=job_id, operation_type="validate", schema_id=schema.schema_id))
        db.commit()
        # Raw SQL so the database rule (not the ORM) is what gets tested.
        db.execute(text("DELETE FROM schemas WHERE schema_id = :id"), {"id": schema.schema_id})
        db.commit()

    with session_factory() as db:
        job = db.get(JobModel, job_id)
    assert job is not None
    assert job.schema_id is None
```

## Paso 6 — CI: ya está hecho (T12)

El paso `Run integration tests` ya existe en `.github/workflows/portfolio-automation-ci.yml`
(lo agregó T12 al reemplazar el archivo completo). **No edites el workflow.** Solo confirma que
existe una vez:
`Select-String -Path ..\..\.github\workflows\portfolio-automation-ci.yml -Pattern "Run integration tests"`
→ exactamente **1** coincidencia.

## Verificación

1. Compuertas → **38 passed, 2 deselected**, ruff y mypy limpios.
2. Integración local:
   `.venv\Scripts\python.exe -m pytest -m integration --timeout=300 -p no:cacheprovider`
   - Con Docker Desktop encendido → **2 passed**.
   - Sin Docker → **2 skipped** con el motivo `Docker not available`. En ese caso escríbelo en
     el reporte como `INTEGRACIÓN NO EJECUTADA LOCALMENTE` (CI la ejecutará). No lo marques
     como verificado.
3. YAML válido:
   `.venv\Scripts\python.exe -c "import yaml; yaml.safe_load(open(r'..\..\.github\workflows\portfolio-automation-ci.yml', encoding='utf-8')); print('yaml ok')"`
   → `yaml ok` (si falta `pyyaml`: `uv pip install -p .venv\Scripts\python.exe pyyaml`).

## Terminado cuando

Las verificaciones 1 y 3 pasan y la 2 da `2 passed` o `2 skipped` explicado. Reporta y marca
`T06` como `DONE`.
