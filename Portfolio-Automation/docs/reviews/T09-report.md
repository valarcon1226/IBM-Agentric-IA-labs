## Tarea T09 — Cobertura para cleaner, transformer y enricher (proyecto 04)
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/tests/test_transformations.py` (nuevo)

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
40 files already formatted
Success: no issues found in 28 source files
...
Name                           Stmts   Miss  Cover
--------------------------------------------------
...
app\services\cleaner.py           36      5    86%
app\services\enricher.py          31      3    90%
...
app\services\transformer.py       17      0   100%
--------------------------------------------------
TOTAL                            578     90    84%
53 passed, 3 deselected, 1 warning in 4.26s
```
Tests: 53 passed, 3 deselected (esperado: 53 passed, 3 deselected) · Cobertura: 84% (vs. 79% en T08, cumple "mayor que")

Dudas o contradicciones encontradas: ninguna
