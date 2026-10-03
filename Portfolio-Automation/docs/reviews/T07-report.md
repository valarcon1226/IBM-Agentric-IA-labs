## Tarea T07 — Schemas guardados en Postgres y usables en `/validate` (proyecto 04)
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/app/services/schemas_repo.py` (nuevo)
- `04-data-cleaning-api/app/api/routes/schemas.py`
- `04-data-cleaning-api/app/api/routes/validate.py`
- `04-data-cleaning-api/tests/test_api.py`
- `04-data-cleaning-api/tests/integration/test_schemas_repo.py` (nuevo)

Desviaciones del código EXACTO: ninguna

Verificación:
```powershell
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
python -m pytest --timeout=60 --cov -p no:cacheprovider
```
<salida real, recortada a lo relevante>
```text
All checks passed!
38 files already formatted
Success: no issues found in 27 source files
...
================= 41 passed, 3 deselected, 1 warning in 3.76s =================
```
Tests: 41 passed, 3 deselected (esperado: 41 passed, 3 deselected) · Cobertura: 79%

```powershell
python -m pytest --timeout=60 -p no:cacheprovider -m integration -v
```
<salida real, recortada a lo relevante>
```text
tests/integration/test_jobs_repo.py::test_job_lifecycle_is_persisted PASSED [ 33%]
tests/integration/test_jobs_repo.py::test_deleting_schema_keeps_its_jobs PASSED [ 66%]
tests/integration/test_schemas_repo.py::test_schema_persists_and_duplicate_is_rejected PASSED [100%]
================ 3 passed, 41 deselected, 2 warnings in 5.27s =================
```
Tests de integración: 3 passed (esperado: 3 passed). Se verificó con `docker ps -a` que no quedó
ningún contenedor de test de Postgres corriendo tras la ejecución (el fixture `pg_engine` es
`scope="session"` y detiene el contenedor al finalizar).

```powershell
Get-ChildItem app -Recurse -Filter *.py | Select-String -Pattern "MOCK_SCHEMAS|^DB: list"
```
Sin coincidencias.

Dudas o contradicciones encontradas: ninguna
