## Tarea T08 — Entrada en Excel (.xlsx) y JSON además de CSV (proyecto 04)
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/app/services/readers.py` (nuevo)
- `04-data-cleaning-api/app/api/routes/clean.py`
- `04-data-cleaning-api/app/services/tasks.py`
- `04-data-cleaning-api/tests/test_api.py`

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
39 files already formatted
Success: no issues found in 28 source files
...
================= 44 passed, 3 deselected, 1 warning in 4.31s =================
```
Tests: 44 passed, 3 deselected (esperado: 44 passed, 3 deselected) · Cobertura: 79%

```powershell
Get-ChildItem app -Recurse -Filter *.py | Select-String -Pattern "read_csv"
```
<salida real>
```text
app\services\readers.py
```
1 coincidencia, en `app\services\readers.py`, como se esperaba.

Dudas o contradicciones encontradas:
- El paso "Antes de empezar" pedía `Select-String -Path requirements.txt -Pattern "openpyxl"` →
  1 coincidencia. Un primer `grep` con el patrón literal no encontró nada por un problema de
  escape en la herramienta; se confirmó leyendo el archivo directamente que
  `openpyxl==3.1.5` sí está en `requirements.txt` y se pudo importar en el venv
  (`python -c "import openpyxl"` → `3.1.5`). No es una contradicción real del repo, solo de la
  primera búsqueda.
