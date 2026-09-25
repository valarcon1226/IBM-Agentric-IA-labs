# T12 — P10: health check real, secreto JWT seguro, tests y CI del backend

**Problemas actuales en `10-docker-compose-lab/backend/`:**
1. `check_db_connection` es un *mock* que siempre devuelve `True`, así que `/health` miente.
2. `/health` responde **200** aunque esté `degraded`, así que el healthcheck de Docker
   (`curl -f /health`) nunca falla.
3. El compose pasa `JWT_SECRET_FILE`, pero `Settings` lo ignora y usa el valor por defecto
   `"insecure-default-secret-change-in-production"`.
4. No hay tests ni CI.

**Objetivo:**
- `/health` real (200/503);
- el secreto se lee del archivo;
- la API se niega a arrancar sin `DATABASE_URL` y sin secreto. El worker y beat de Celery **no**
  se ven afectados: importan `Settings`, pero no lo exigen;
- todo cubierto por 5 tests y en CI.

El código de esta tarea **ya se ejecutó**: 5 passed, ruff y mypy limpios, 61% de cobertura.

**Archivos que puedes tocar:**
- `10-docker-compose-lab/backend/src/config.py` · `src/main.py`
- `10-docker-compose-lab/backend/src/celery_app.py` · `src/tasks.py` (**solo** `ruff check --fix` y `ruff format`, nada a mano)
- `10-docker-compose-lab/backend/pyproject.toml` · `requirements-dev.txt` · `tests/__init__.py` · `tests/conftest.py` · `tests/test_main.py` (todos nuevos)
- `10-docker-compose-lab/.gitignore`
- `10-docker-compose-lab/EXECUTION_PLAN.md`
- `10-docker-compose-lab/docs/RISK-ANALYSIS.md` (solo columnas Status y Fix de DL-R01, R02, R03, R05, R10)
- `Portfolio-Automation/README.md` (fila 10)
- `.github/workflows/portfolio-automation-ci.yml` (en la raíz del repositorio git, una carpeta **arriba** de `Portfolio-Automation`)

## Antes de empezar

- `T11` en `DONE` (esta tarea usa `scripts/sync_readme.py`, creado en T11). No depende de T01–T10.
- `Select-String -Path 10-docker-compose-lab\backend\src\main.py -Pattern "Mock checking DB"` → 1 coincidencia.

## Paso 1 — `backend/src/config.py` (reemplazo completo)

EXACTO:

```python
"""Configuration settings for the FastAPI Gateway."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables.

    Shared by the API and the Celery worker/beat. Only the API requires DATABASE_URL and a JWT
    secret (see ``require_api_settings``), so the workers can start with a smaller environment.
    """

    APP_NAME: str = "Portfolio Automation Gateway"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    JWT_SECRET: str | None = None
    JWT_SECRET_FILE: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _load_jwt_secret_file(self) -> "Settings":
        if not self.JWT_SECRET and self.JWT_SECRET_FILE:
            self.JWT_SECRET = Path(self.JWT_SECRET_FILE).read_text(encoding="utf-8").strip()
        return self

    @property
    def get_celery_broker_url(self) -> str:
        """Returns the celery broker URL, falling back to REDIS_URL if not set."""
        return self.CELERY_BROKER_URL or self.REDIS_URL


def require_api_settings(s: Settings) -> None:
    """Fail fast if the API is started without the settings it cannot run without."""
    missing = [
        name
        for name, value in (("DATABASE_URL", s.DATABASE_URL), ("JWT_SECRET", s.JWT_SECRET))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required settings: {', '.join(missing)} (JWT_SECRET_FILE also works)"
        )


settings = Settings()
```

## Paso 2 — `backend/src/main.py` (reemplazo completo)

EXACTO:

```python
"""
FastAPI Gateway — Portfolio Automation Stack

Central API gateway for the automation portfolio. Serves as the entry point
for all backend operations and provides health monitoring endpoints.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import create_engine, text

from .config import require_api_settings, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

require_api_settings(settings)
assert settings.DATABASE_URL is not None  # guaranteed by require_api_settings
_db_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


async def check_redis_connection(url: str) -> bool:
    """Check connection to Redis."""
    try:
        client = redis.from_url(url, socket_timeout=2.0)
        await client.ping()
        await client.close()
        return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return False


async def check_db_connection() -> bool:
    """Run SELECT 1 against the database without blocking the event loop."""

    def _ping() -> None:
        with _db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    try:
        await asyncio.to_thread(_ping)
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info(f"Starting up {settings.APP_NAME}...")
    if not await check_redis_connection(settings.REDIS_URL):
        logger.warning("Redis is not available on startup.")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Central API gateway for the automation portfolio.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify in production to restrict origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)


@app.get("/", summary="Root Endpoint")
async def root() -> dict[str, str]:
    """Welcome endpoint returning basic API information."""
    return {
        "message": f"Welcome to the {settings.APP_NAME}",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


@app.get("/health", summary="Health Check")
async def health_check() -> JSONResponse:
    """Real dependency check. Returns 503 when a dependency is down so that the
    Docker healthcheck (curl -f /health) marks the container unhealthy."""
    redis_ok = await check_redis_connection(settings.REDIS_URL)
    db_ok = await check_db_connection()
    healthy = redis_ok and db_ok
    body: dict[str, Any] = {
        "status": "healthy" if healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "api": "up",
            "database": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
    }
    return JSONResponse(status_code=200 if healthy else 503, content=body)


@app.get("/version", summary="Version Info")
async def version_info() -> dict[str, str]:
    """Returns the current application version."""
    return {"app_name": settings.APP_NAME, "version": settings.APP_VERSION}
```

## Paso 3 — `backend/pyproject.toml` (nuevo)

EXACTO:

```toml
[project]
name = "portfolio-gateway"
version = "1.0.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = [".venv"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["B008"]

[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
ignore_missing_imports = true
exclude = ["^\\.venv/"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra"

[tool.coverage.run]
source = ["src"]
```

## Paso 4 — `backend/requirements-dev.txt` (nuevo)

EXACTO:

```
-r requirements.txt
pytest==8.3.2
pytest-cov==7.1.0
pytest-timeout==2.4.0
ruff==0.16.8
mypy==2.3.1
```

## Paso 5 — tests (nuevos)

`backend/tests/__init__.py`: vacío.

`backend/tests/conftest.py`. EXACTO:

```python
import os

# Inert values so src.main can be imported; nothing here opens a connection.
TEST_ENV = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "JWT_SECRET": "test-secret",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
```

`backend/tests/test_main.py`. EXACTO:

```python
import pytest
from fastapi.testclient import TestClient

from src import main
from src.config import Settings, require_api_settings

client = TestClient(main.app)


def _deps(monkeypatch, *, redis_ok: bool, db_ok: bool) -> None:
    async def fake_redis(url):
        return redis_ok

    async def fake_db():
        return db_ok

    monkeypatch.setattr(main, "check_redis_connection", fake_redis)
    monkeypatch.setattr(main, "check_db_connection", fake_db)


def test_health_ok_when_dependencies_up(monkeypatch):
    _deps(monkeypatch, redis_ok=True, db_ok=True)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_health_503_when_redis_down(monkeypatch):
    _deps(monkeypatch, redis_ok=False, db_ok=True)
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["services"]["redis"] == "down"


def test_health_503_when_database_down(monkeypatch):
    _deps(monkeypatch, redis_ok=True, db_ok=False)
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["services"]["database"] == "down"


def test_jwt_secret_is_read_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    secret_file = tmp_path / "jwt_secret"
    secret_file.write_text("s3cret\n", encoding="utf-8")

    s = Settings(_env_file=None, JWT_SECRET_FILE=str(secret_file))  # type: ignore[call-arg]

    assert s.JWT_SECRET == "s3cret"


def test_api_refuses_to_start_without_secret_or_database(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL, JWT_SECRET"):
        require_api_settings(Settings(_env_file=None))  # type: ignore[call-arg]
```

Nota: los dos `# type: ignore[call-arg]` de este archivo son **parte del código EXACTO** (igual
que en `04-data-cleaning-api/tests/test_config.py`). No agregues otros.

## Paso 6 — entorno y formato (desde `10-docker-compose-lab\backend`)

```powershell
uv venv -p 3.12 .venv
uv pip install -p .venv\Scripts\python.exe -r requirements-dev.txt
.venv\Scripts\ruff.exe check src tests --fix
.venv\Scripts\ruff.exe format src tests
```

Lo único que deben cambiar `--fix` y `format` son el orden de imports y el formato de
`celery_app.py` y `tasks.py`. Si `ruff` cambia algo más, repórtalo.

## Paso 7 — `10-docker-compose-lab/.gitignore`

Agrega al final estas líneas. EXACTO:

```
.venv/
.coverage
coverage.xml
test-results/
.mypy_cache/
.ruff_cache/
```

## Paso 8 — CI: `.github/workflows/portfolio-automation-ci.yml` (reemplazo completo)

Reemplaza el archivo completo por este contenido. Incluye el paso de integración de T06, y
agrega el backend de P10 y la comprobación del README de P10. EXACTO:

```yaml
name: Portfolio Automation CI

on:
  pull_request:
    paths:
      - "Portfolio-Automation/**"
      - ".github/workflows/portfolio-automation-ci.yml"
  push:
    branches:
      - main
    paths:
      - "Portfolio-Automation/**"
      - ".github/workflows/portfolio-automation-ci.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  python-service:
    name: ${{ matrix.project }}
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        # Only projects with real code and tests are listed. Add a project here once it has both.
        include:
          - project: 04-data-cleaning-api
            src: app
            slug: 04-data-cleaning-api
          - project: 10-docker-compose-lab/backend
            src: src
            slug: 10-backend
    defaults:
      run:
        working-directory: Portfolio-Automation/${{ matrix.project }}
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: Portfolio-Automation/${{ matrix.project }}/requirements*.txt

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Lint
        run: ruff check ${{ matrix.src }} tests

      - name: Check formatting
        run: ruff format --check ${{ matrix.src }} tests

      - name: Type-check
        run: mypy ${{ matrix.src }}

      - name: Run tests
        run: >-
          pytest --timeout=60
          --cov --cov-report=term --cov-report=xml
          --junitxml=test-results/junit.xml

      - name: Run integration tests
        if: ${{ hashFiles(format('Portfolio-Automation/{0}/tests/integration/**', matrix.project)) != '' }}
        env:
          REQUIRE_DOCKER: "1"
        run: pytest -m integration --timeout=300 --junitxml=test-results/junit-integration.xml

      - name: Upload test artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.slug }}-test-results-${{ github.run_id }}-${{ github.run_attempt }}
          path: |
            Portfolio-Automation/${{ matrix.project }}/test-results/
            Portfolio-Automation/${{ matrix.project }}/coverage.xml
          if-no-files-found: ignore
          retention-days: 7

  readme-sync:
    name: 10-docker-compose-lab README sync
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: README sections match .env.example, docker-compose.yml and init-db.sh
        working-directory: Portfolio-Automation/10-docker-compose-lab
        run: python scripts/sync_readme.py --check
```

## Paso 9 — `10-docker-compose-lab/EXECUTION_PLAN.md`

En "### 4. Backend", cambia el **primer** `- [ ]` (el de `backend/tests/`) a `- [x]` y agrega
debajo `  - Done (T12): <N> passed, cobertura <C> (salida real)`. No toques los demás ítems.

## Paso 10 — `Portfolio-Automation/README.md`

En la fila `| 10 |`, reemplaza el texto de Evidence
`Compose file + backend skeleton; not verified in CI` por
`Backend: <N> tests · <C> cov · CI; compose not yet run end to end`.
**No** cambies el estado `Scaffolded`: el stack completo aún no se ha levantado.

## Paso 11 — `10-docker-compose-lab/docs/RISK-ANALYSIS.md`

En las filas `DL-R01`, `DL-R02`, `DL-R03`, `DL-R05` y `DL-R10`, cambia Status a
`**Observed → fixed**` y Fix a `T12 (done)`. En `DL-R09` cambia Status a `Mitigated` y Fix a
`T12 (done)`. En el README de P10, en la nota de estado del inicio, reemplaza
`four are Critical and open` y el paréntesis que le sigue por
`the remaining Critical one is DL-R11 (full stack never started)`. No toques otras filas.

## Verificación

Desde `10-docker-compose-lab\backend`:

1. `.venv\Scripts\ruff.exe check src tests` → `All checks passed!`
2. `.venv\Scripts\ruff.exe format --check src tests` → `... files already formatted`
3. `.venv\Scripts\mypy.exe src` → `Success: no issues found in 5 source files`
4. `.venv\Scripts\python.exe -m pytest --timeout=60 --cov -p no:cacheprovider` → **5 passed**, TOTAL ≈ 61%
5. `Select-String -Path src\*.py -Pattern "Mock checking DB|insecure-default-secret"` → **sin coincidencias**
6. YAML válido (desde `Portfolio-Automation\04-data-cleaning-api`):
   `.venv\Scripts\python.exe -c "import yaml; d=yaml.safe_load(open(r'..\..\.github\workflows\portfolio-automation-ci.yml', encoding='utf-8')); print(sorted(d['jobs']), [m['project'] for m in d['jobs']['python-service']['strategy']['matrix']['include']])"`
   → `['python-service', 'readme-sync'] ['04-data-cleaning-api', '10-docker-compose-lab/backend']`
7. Las compuertas del proyecto 04 dan el mismo número de tests que antes de esta tarea (T12 no toca el 04).

## Terminado cuando

Las 7 verificaciones pasan. Reporta y marca `T12` como `DONE`.
