## Tarea T05 — `/jobs` lee Postgres; se eliminan los mocks y los modelos duplicados (proyecto 04)
Estado: DONE
Archivos modificados:
- `04-data-cleaning-api/app/api/routes/jobs.py`
- `04-data-cleaning-api/app/models/domain.py`
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
33 files already formatted
Success: no issues found in 26 source files
...
38 passed, 1 warning in 3.93s
```
Tests: 38 passed (esperado: 38) · Cobertura: 79%

```powershell
Get-ChildItem app -Recurse -Filter *.py | Select-String -Pattern "MOCK_JOBS|CleanOptions|SchemaCreate"
```
<salida real, recortada a lo relevante>
```text
(sin coincidencias)
```

Dudas o contradicciones encontradas:
- Durante la edición generé un archivo temporal `app/models/domain.py.new` (contenido idéntico
  al `domain.py` final) y lo descarté enseguida, pero el entorno bloqueó todos los intentos de
  borrarlo ("Permission denied and could not request permission from user" en
  `Remove-Item`/`del`, repetido varias veces). No es un `.py` y no coincide con ninguno de los
  patrones de verificación (confirmado con `Select-String`), así que no afecta los resultados,
  pero queda como residuo que requiere borrado manual fuera de esta sesión.
