## Tarea T04 — Las tareas Celery guardan su estado real (proyecto 04)
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/app/services/tasks.py`
- `04-data-cleaning-api/tests/test_tasks.py` (nuevo)

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
33 files already formatted
Success: no issues found in 26 source files
...
34 passed, 1 warning in 3.94s
```
Tests: 34 passed (esperado: 34) · Cobertura: 70%

```powershell
Get-ChildItem app -Recurse -Filter *.py | Select-String -Pattern "def update_job_status"
```
<salida real, recortada a lo relevante>
```text
(sin coincidencias)
```

Dudas o contradicciones encontradas: ninguna
