## Tarea T02 — Repositorio de jobs `jobs_repo.py`
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/app/services/jobs_repo.py` (nuevo)

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
app\services\jobs_repo.py        31     31     0%
-------------------------------------------------
TOTAL                           523    206    61%
29 passed, 1 warning in 5.01s
```
Tests: 29 passed (esperado: 29) · Cobertura: 61% (módulo nuevo sin tests directos; se cubre en T06)

```powershell
Select-String -Path app\services\jobs_repo.py -Pattern "def create_job|def get_job|def set_status"
```
<salida real>
```text
app\services\jobs_repo.py:15:def create_job(
app\services\jobs_repo.py:30:def get_job(db: Session, job_id: UUID) -> JobModel | None:
app\services\jobs_repo.py:34:def set_status(
```
3 coincidencias (esperado: 3) — OK.

Dudas o contradicciones encontradas: ninguna
