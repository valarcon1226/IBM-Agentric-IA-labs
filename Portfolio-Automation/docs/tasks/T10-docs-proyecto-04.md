# T10 — Actualizar la documentación del proyecto 04 con lo construido en T01–T09

**Objetivo:** que README, análisis de riesgos, matriz de trazabilidad y README raíz digan
exactamente lo que el código hace ahora. **No se toca código.**

**Archivos que puedes tocar:**
- `04-data-cleaning-api/README.md`
- `04-data-cleaning-api/docs/RISK-ANALYSIS.md`
- `04-data-cleaning-api/docs/TRACEABILITY-MATRIX.md`
- `README.md` (raíz de `Portfolio-Automation`)

## Antes de empezar

1. `T09` en `DONE`.
2. Corre las compuertas y **anota** estos dos números de la salida real: `N` = número de
   `passed`, y `C` = el porcentaje de la fila `TOTAL`. (Esperado: `N` = 53.) Úsalos en toda
   esta tarea donde diga `<N>` y `<C>`. No los redondees ni los inventes.

## Paso 1 — `04-data-cleaning-api/README.md`

1a. En la tabla "Current status", reemplaza estas tres filas:

```
| Async job status and result retrieval             | **Stubbed** — job state is not persisted yet |
| User-defined schemas usable in `/validate`        | **Not yet** — schemas are kept in memory only |
| Excel / JSON input                                | **Not yet** — CSV only |
```

por. EXACTO:

```
| Async job status and result retrieval (Postgres)  | Working, tested (unit + integration) |
| User-defined schemas persisted and usable in `/validate` | Working, tested (unit + integration) |
| CSV, Excel (.xlsx) and JSON input                 | Working, tested |
| Full stack run (`docker compose up`) end to end   | **Not verified yet** (DC-JOB-004, manual) |
```

1b. Reemplaza la línea que empieza con `**Evidence:**` por:
`**Evidence:** <N> passing unit/API tests + 3 integration tests (real Postgres, run in CI), <C> line coverage, `ruff` + `mypy` clean, run in CI on every push.`

1c. En la sección `## 5. Database Schema`, reemplaza el párrafo:
"Applied by `init-db.sql` (mounted into the `db` container). The tables exist today; the API does
not read or write them yet — see "Current status" (jobs and schemas are still in memory)."
por:
"Applied by `init-db.sql` (mounted into the `db` container). `jobs` is written by the API
(`PENDING`) and by the Celery worker (`PROCESSING` → `COMPLETED`/`FAILED`); `schemas` stores
user-defined validation schemas."

1d. En `### 6.1 POST /api/v1/clean`, reemplaza la frase "Cleans a CSV." por
"Cleans a `.csv`, `.xlsx` or `.json` (array of records) file; other extensions return `415`."

1e. En `### 6.2 POST /api/v1/validate`, reemplaza
"Today only the built-in `user_schema`\n(`id: int`, `name: str`, `age: int >= 0`) is available."
por
"`schema_id` is either the built-in `user_schema` (`id: int`, `name: str`, `age: int >= 0`) or
the `id` of a schema created with `POST /api/v1/schemas`."

1f. Reemplaza **todo** desde la línea `### 6.6 GET /api/v1/jobs/{job_id} — *stub*` hasta
justo antes de `## 7. Docker Services` por. EXACTO:

````markdown
### 6.6 GET /api/v1/jobs/{job_id}
```bash
curl "http://localhost:8000/api/v1/jobs/3f1c9a52-8b0e-4d2a-9c7e-5a1b2c3d4e5f" \
  -H "Authorization: Bearer $API_KEY"
```
**Response:**
```json
{
  "job_id": "3f1c9a52-8b0e-4d2a-9c7e-5a1b2c3d4e5f",
  "status": "COMPLETED",
  "operation_type": "clean",
  "error_message": null,
  "created_at": "2026-09-24T10:00:00Z",
  "started_at": "2026-09-24T10:00:02Z",
  "completed_at": "2026-09-24T10:00:15Z"
}
```
`status` is `PENDING` | `PROCESSING` | `COMPLETED` | `FAILED`. Unknown id → `404`; malformed id → `422`.

### 6.7 GET /api/v1/jobs/{job_id}/result
```bash
curl "http://localhost:8000/api/v1/jobs/3f1c9a52-8b0e-4d2a-9c7e-5a1b2c3d4e5f/result" \
  -H "Authorization: Bearer $API_KEY"
```
**Response:**
```json
{
  "job_id": "3f1c9a52-8b0e-4d2a-9c7e-5a1b2c3d4e5f",
  "download_url": "http://minio:9000/data-cleaning-api/results/cleaned_3f1c9a52-....csv?X-Amz-Signature=...",
  "expires_in": 3600
}
```
Unknown job → `404`; job not `COMPLETED` → `400`. Results are always CSV.

### 6.8 POST /api/v1/schemas
`fields` maps column → type, one of `int`, `float`, `str`, `bool`, `datetime`
(anything else → `422`). A duplicate `name` → `409`.
```bash
curl -X POST "http://localhost:8000/api/v1/schemas" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "customers", "fields": {"id": "int", "email": "str"}}'
```
**Response:**
```json
{"status": "success", "schema_id": "9b2e4c1a-7d3f-4e8a-b5c6-0d1e2f3a4b5c",
 "data": {"id": "9b2e4c1a-7d3f-4e8a-b5c6-0d1e2f3a4b5c", "name": "customers",
          "fields": {"id": "int", "email": "str"}}}
```

### 6.9 GET /api/v1/schemas
```bash
curl "http://localhost:8000/api/v1/schemas" -H "Authorization: Bearer $API_KEY"
```
**Response:**
```json
{"status": "success", "schemas": [{"id": "9b2e4c1a-7d3f-4e8a-b5c6-0d1e2f3a4b5c",
                                   "name": "customers", "fields": {"id": "int", "email": "str"}}]}
```

````

1g. En `## 8. File Structure`, dentro del bloque de código:
- en la línea `│   ├── services/ ...` agrega `, jobs_repo, schemas_repo, readers` después de `tasks (Celery tasks)`;
- en `tests/`, agrega debajo de `test_config.py` estas líneas:
  ```
  │   ├── test_models.py
  │   ├── test_tasks.py
  │   ├── test_transformations.py
  │   └── integration/       real Postgres via testcontainers (pytest -m integration)
  ```
  y cambia el `└──` de `test_config.py` por `├──`.

## Paso 2 — `04-data-cleaning-api/docs/RISK-ANALYSIS.md`

Cambia **solo** las columnas `Status` y `Response` de estas filas (la tabla tiene esas columnas
en las posiciones 6 y 7):

| Risk ID | Status (nuevo) | Response (nuevo) |
| ------- | -------------- | ---------------- |
| DC-R02 | `Covered` | `Every cleaning option has a unit test (test_cleaner.py, test_transformations.py).` |
| DC-R04 | `**Observed → fixed**` | `Job state persisted in Postgres by API and worker; status/result endpoints read it. Unit tests + integration test on real Postgres.` |
| DC-R07 | `**Observed → fixed**` | `Schemas persisted in Postgres; /validate accepts built-in or stored schema id; duplicate → 409.` |
| DC-R09 | `**Observed → fixed**` | `CSV, .xlsx and JSON records accepted via app/services/readers.py; other extensions → 415.` |
| DC-R11 | `Covered` | `Unit tests for all five transforms and both enrichers.` |

## Paso 3 — `04-data-cleaning-api/docs/TRACEABILITY-MATRIX.md`

3a. Cambia estas filas a `Implemented` y pon en la última columna exactamente:

| Scenario ID | Automated test |
| ----------- | -------------- |
| DC-CLEAN-005 | `tests/test_transformations.py::test_handle_nulls_drop_removes_incomplete_rows`, `tests/test_transformations.py::test_handle_nulls_fill_value_uses_given_value` |
| DC-CLEAN-009 | `tests/test_api.py::test_clean_accepts_xlsx`, `tests/test_api.py::test_clean_accepts_json_records`, `tests/test_api.py::test_clean_rejects_unsupported_extension` |
| DC-VAL-004 | `tests/test_api.py::test_created_schema_is_usable_in_validate` |
| DC-SCH-003 | `tests/integration/test_schemas_repo.py::test_schema_persists_and_duplicate_is_rejected` |
| DC-JOB-001 | `tests/test_api.py::test_unknown_job_returns_404`, `tests/test_api.py::test_invalid_job_id_returns_422` |
| DC-JOB-002 | `tests/test_tasks.py::test_clean_task_marks_completed_with_output_path`, `tests/test_tasks.py::test_clean_task_marks_failed_on_error`, `tests/integration/test_jobs_repo.py::test_job_lifecycle_is_persisted` |
| DC-JOB-003 | `tests/test_api.py::test_job_result_returns_presigned_url`, `tests/test_api.py::test_job_result_not_completed_returns_400` |
| DC-TRF-001 | `tests/test_transformations.py` (5 tests: pivot, melt, merge, split, aggregate) |
| DC-ENR-001 | `tests/test_transformations.py::test_validate_emails_flags_invalid_and_missing`, `tests/test_transformations.py::test_normalize_phones_formats_valid_and_flags_invalid` |

3b. En la fila `DC-JOB-001`, cambia el texto del escenario a
`Unknown job returns 404; malformed id returns 422`.

3c. Cuenta con PowerShell (no a mano):
```powershell
(Select-String -Path docs\TRACEABILITY-MATRIX.md -Pattern "\| Implemented +\|").Count
(Select-String -Path docs\TRACEABILITY-MATRIX.md -Pattern "\| Not Implemented +\|").Count
```
Llama `I` y `O` a los resultados. Reemplaza la línea que empieza con `**Status:**` por:
`**Status:** <I> of <I+O> scenarios automated by <N> unit/API tests and 3 integration tests. The other <O> are `Not Implemented` and have no test path listed.`
(Esperado: **I = 32, O = 1** — la única abierta es DC-JOB-004, que es manual. Si obtienes
otros números, detente y reporta.)

3d. En "Coverage interpretation", reemplaza el párrafo completo que empieza con
"Every scenario maps to at least one risk" y termina en "and multi-format input." por. EXACTO:

```
Every scenario maps to at least one risk in [`RISK-ANALYSIS.md`](RISK-ANALYSIS.md). No Critical
risk has an open automated scenario. The remaining gap is DC-JOB-004 (manual full-stack run with
Docker Compose), which must pass before calling the service production-ready.
```

3e. Reemplaza "Line coverage from `pytest --cov` is 58%" por "Line coverage from `pytest --cov` is <C>".

## Paso 4 — `README.md` raíz (`Portfolio-Automation\README.md`)

4a. En la fila de `04`, reemplaza `27 tests · 58% cov` por `<N> tests + 3 integration · <C> cov`.
4b. En la tabla Roadmap, cambia el estado de la fila `3b` de `Next` a `Done`.
4c. En la fila de `04`, cambia `Cleans, validates and transforms CSV data` por
`Cleans, validates and transforms CSV/Excel/JSON data`.

## Verificación

1. `Select-String -Path README.md, docs\*.md -Pattern "Stubbed|stub\*|in memory|Not yet|CSV only"`
   (desde `04-data-cleaning-api`) → **sin coincidencias**.
2. `Select-String -Path docs\TRACEABILITY-MATRIX.md -Pattern "\| Not Implemented"` → **solo** la
   fila `DC-JOB-004`.
3. Compuertas → siguen en `<N> passed, 3 deselected` (no se tocó código).

## Terminado cuando

Las tres pasan. Reporta, incluyendo `N`, `C`, `I` y `O`, y marca `T10` como `DONE`.
