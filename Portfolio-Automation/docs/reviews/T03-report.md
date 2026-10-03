## Tarea T03 — Las rutas que encolan crean el job en Postgres antes de encolar
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/app/services/jobs_repo.py` (agregado `logging`, `logger`, `mark_enqueue_failed`)
- `04-data-cleaning-api/app/api/routes/clean.py` (reemplazo completo)
- `04-data-cleaning-api/app/api/routes/transform.py` (reemplazo completo)
- `04-data-cleaning-api/app/api/routes/enrich.py` (reemplazo completo)
- `04-data-cleaning-api/tests/test_api.py` (imports, fixture `fake_jobs`, firmas de 3 tests, 2 tests nuevos)

Desviaciones del código EXACTO: ninguna

Verificación:
```powershell
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
python -m pytest --timeout=60 --cov -p no:cacheprovider -q
```
<salida real, recortada a lo relevante>
```text
All checks passed!
32 files already formatted
Success: no issues found in 26 source files
...
app\api\routes\clean.py          48     10    79%
app\api\routes\enrich.py         25      4    84%
app\api\routes\transform.py      26      0   100%
app\services\jobs_repo.py        38     23    39%
-------------------------------------------------
TOTAL                           549    196    64%
31 passed, 1 warning in 6.04s
```
Tests: 31 passed (esperado: 31) · Cobertura: 64%

```powershell
Select-String -Path app\api\routes\clean.py, app\api\routes\transform.py, app\api\routes\enrich.py -Pattern "jobs_repo.create_job"
```
<salida real>
```text
app\api\routes\clean.py:55:    jobs_repo.create_job(db, job_id, "clean", obj_key)
app\api\routes\transform.py:26:    jobs_repo.create_job(db, job_id, "transform", request.file_path)
app\api\routes\enrich.py:25:    jobs_repo.create_job(db, job_id, "enrich", request.file_path)
```
3 coincidencias (esperado: 3) — OK.

Dudas o contradicciones encontradas: ninguna
