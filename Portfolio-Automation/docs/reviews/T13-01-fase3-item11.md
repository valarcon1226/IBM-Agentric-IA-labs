# T13-01 — Fase 3, item 11: healthchecks + unit → integration → E2E

> Copilot escribió este reporte fuera del repo (su sesión estaba limitada a
> `01-smart-data-intake`); Claude lo copió aquí y aplicó la corrección de D10.

## Tarea 1 — Healthchecks

### Corrección a D10 (`docs/reviews/DECISIONES-01.md`)

D10 afirma incorrectamente que `chainguard/minio` no tiene `mc`. Es falso:

```
docker exec 01-smart-data-intake-minio-1 mc ready local
The cluster 'local' is ready
```

Texto corregido sugerido para D10: "`chainguard/minio` sí incluye el binario
`mc`; `mc ready local` devuelve `The cluster 'local' is ready` y se usa como
healthcheck del servicio `minio`."

### Cambios en `docker-compose.yml`

- `minio`: `healthcheck: {test: ["CMD", "mc", "ready", "local"], interval: 10s, retries: 10}`
- `api`: `healthcheck: {test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"], interval: 10s, retries: 10}`; `depends_on.minio.condition: service_healthy` (antes `service_started`).
- `dashboard`: `healthcheck: {test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"], interval: 10s, retries: 10}`; se agregó `depends_on.api.condition: service_healthy` (antes no dependía de nada).
- `n8n`: `healthcheck: {test: ["CMD", "wget", "-qO-", "http://localhost:5678/healthz"], interval: 10s, retries: 10}`.

### Verificación

```
docker exec 01-smart-data-intake-minio-1 mc ready local
The cluster 'local' is ready

docker compose --env-file .env.example up -d --wait
 Container 01-smart-data-intake-postgres-1  Healthy
 Container 01-smart-data-intake-redis-1     Healthy
 Container 01-smart-data-intake-minio-1     Healthy
 Container 01-smart-data-intake-api-1       Healthy
 Container 01-smart-data-intake-dashboard-1 Healthy
 Container 01-smart-data-intake-n8n-1       Healthy

docker compose --env-file .env.example ps
NAME                               STATUS
01-smart-data-intake-api-1         Up (healthy)
01-smart-data-intake-dashboard-1   Up (healthy)
01-smart-data-intake-minio-1       Up (healthy)
01-smart-data-intake-n8n-1         Up (healthy)
01-smart-data-intake-postgres-1    Up (healthy)
01-smart-data-intake-redis-1       Up (healthy)
```

Los 6 servicios quedan `healthy`. En `EXECUTION_PLAN.md` se marcó el ítem 2
("Write `docker-compose.yml` with only `postgres`, `redis`, `minio`") y la
línea de Definition-of-Done "`docker compose up -d` brings up all 6 services
healthy" como `[x]`.

Nota: el stack se levanta con `docker compose --env-file .env.example up -d
--wait` porque no existe un `.env` real en este checkout (regla del proyecto:
nunca tocar archivos `.env`); los contenedores ya corrían así desde antes de
esta tarea (ver `com.docker.compose.project.environment_file` en las labels).

## Tarea 2 — EXECUTION_PLAN item 11: unit → integration → E2E

### Archivo nuevo: `backend/tests/test_integration_e2e.py`

- Marcado con `pytestmark = pytest.mark.integration`; el flujo E2E completo
  lleva además `@pytest.mark.e2e`. Ambos markers están registrados en
  `backend/pyproject.toml` (`markers = [...]`) y excluidos del run por defecto
  vía `addopts = "-ra -m \"not integration and not e2e\""`, de modo que la
  suite unitaria sigue corriendo sin Docker.
- Lee configuración de conexión desde variables `E2E_*` (API_BASE_URL,
  API_KEY, POSTGRES_HOST/PORT/USER/PASSWORD/DB, REDIS_HOST/PORT,
  MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/BUCKET_NAME), con los valores por
  defecto documentados en `.env.example`. Se usó el prefijo `E2E_` — y no los
  nombres planos `API_KEY`/`POSTGRES_USER`/etc. — porque `tests/conftest.py`
  ya hace `os.environ.setdefault(...)` con esos nombres planos para que la
  suite unitaria pueda construir `Settings()` sin Docker (p. ej.
  `API_KEY=test`); reutilizarlos habría mandado esa clave de prueba contra el
  stack real en `localhost:8001`, que corre con la clave real de
  `.env.example` (`change_me_api_key`) — esto se detectó como un 401 real
  durante el desarrollo y se corrigió usando los nombres `E2E_*`.
- `test_health_endpoint_reports_healthy` / `test_upload_requires_api_key`:
  pruebas de integración contra el endpoint real.
- `test_upload_review_and_approve_flow_against_real_stack` (E2E): sube
  `customers.csv` (el archivo real del repo, 3 filas: limpia / ambigua /
  fallida), hace polling de `GET /api/v1/intake/{id}` hasta `status ==
  "completed"` (timeout 30 s), valida `clean_rows == 1`, `ambiguous_rows ==
  1`, `failed_rows == 1`; aprueba la fila ambigua vía `POST
  .../{id}/review`; valida que la cola de revisión queda vacía y que
  `clean_data` tiene 2 filas (la original limpia + la aprobada) y
  `error_log` tiene 1. Un bloque `finally` limpia: `DELETE FROM uploads`
  (cascada a `clean_data`/`error_log` por `ON DELETE CASCADE`), cualquier
  resto en `review_queue`, y el objeto en MinIO.
- Fixture `stack` (`scope="module"`): hace `GET /health` con timeout corto; si
  falla, `pytest.skip(...)`. Verificado manualmente apuntando
  `E2E_API_BASE_URL` a un puerto inexistente: los 3 tests quedan `SKIPPED` en
  vez de fallar.

### Resultados

Suite unitaria (sin marcar integración/E2E, comportamiento por defecto):

```
cd backend
python -m pytest --timeout=60 --cov -p no:cacheprovider -v
...
21 passed, 3 deselected, 1 warning in 2.45s
TOTAL coverage: 88%
```

Suite integración + E2E (stack arriba, healthy):

```
python -m pytest tests/test_integration_e2e.py -m "integration or e2e" --timeout=60 -p no:cacheprovider -v
tests/test_integration_e2e.py::test_health_endpoint_reports_healthy PASSED
tests/test_integration_e2e.py::test_upload_requires_api_key PASSED
tests/test_integration_e2e.py::test_upload_review_and_approve_flow_against_real_stack PASSED
3 passed in 1.08s
```

Skip limpio sin stack (verificación, no parte del run normal):

```
$env:E2E_API_BASE_URL = "http://localhost:59999"
python -m pytest tests/test_integration_e2e.py -m "integration or e2e" ...
3 skipped in 4.41s
```

Limpieza verificada tras el E2E (sin filas residuales de esa corrida en
`uploads`/`clean_data`/`error_log`/`review_queue`/MinIO).

### Quality gates

```
python -m ruff check app tests
All checks passed!

python -m ruff format --check app tests
16 files already formatted

python -m mypy app
Success: no issues found in 8 source files
```

### Archivos modificados
- `01-smart-data-intake/docker-compose.yml`
- `01-smart-data-intake/EXECUTION_PLAN.md`
- `01-smart-data-intake/backend/pyproject.toml`
- `01-smart-data-intake/backend/tests/test_integration_e2e.py` (nuevo)

### Desviaciones del código EXACTO
Ninguna (esta tarea no incluye bloques `EXACTO`).

### Tests
Unit: 21 passed (3 deselected). Integración + E2E: 3 passed. Cobertura: 88%
(solo medida en la suite unitaria, como en gates previos).

### Dudas o contradicciones encontradas
- No pude acceder a `../docs/reviews/DECISIONES-01.md` para corregir D10 in
  situ, ni escribir este informe en `docs/reviews/`: el entorno bloquea toda
  lectura/escritura fuera de `01-smart-data-intake` (confirmado con `view`,
  `Test-Path`, `Get-Content` y `git show`, todos denegados sin posibilidad de
  aprobación en modo no interactivo). El texto de corrección de D10 queda
  arriba para pegarlo manualmente.
