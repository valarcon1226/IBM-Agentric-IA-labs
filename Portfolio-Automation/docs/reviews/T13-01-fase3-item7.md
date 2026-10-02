# T13-01 — Fase 3, ítem 7

- 7: `[ ]` procesamiento background: clean → `clean_data`, failed → `error_log`, ambiguous → Redis `review_queue`; la implementación ya existía, pero usaba `RPUSH`; se cambió a `LPUSH` como pide el ítem. `.\.venv\Scripts\python.exe -m pytest tests/test_processing.py -q` → 4 passed, incluidos los fakes de clean/failed/ambiguous, duplicado y estado failed cuando MinIO falla. Verificación del upload en el stack pendiente: needs Docker (D7).
- Regresión LPUSH: al cambiar el fake a `lpush`, el test focalizado falló con `AttributeError` al detectar `rpush`; tras el cambio, el mismo test → 1 passed.
- Test añadido: fallo de MinIO marca el upload como `failed` y usa `upload_id` parametrizado.
- Compuertas desde `01-smart-data-intake/backend/`: `.\.venv\Scripts\ruff.exe check .` → `All checks passed!`; `.\.venv\Scripts\ruff.exe format --check .` → `15 files already formatted`; `.\.venv\Scripts\python.exe -m mypy app` → `Success: no issues found in 8 source files`; `.\.venv\Scripts\python.exe -m pytest --cov=app -q` → `15 passed`, 0 failed, cobertura 87% (1 warning deprecación de Starlette/AnyIO).
- El comando directo `pytest tests/test_processing.py -q` no se reconoció en PATH. El ejecutable `.\.venv\Scripts\mypy.exe app` falló con `uv trampoline failed to canonicalize script path`; el mismo mypy del venv ejecutado como módulo pasó sin errores.
- Ruff formateó tres archivos y aplicó autofixes de lint; las separaciones de literales SQL preservan el SQL parametrizado.
- Verificación Docker de MinIO/Postgres/Redis y muestra CSV no ejecutada: needs Docker (D7); no se ejecutó `docker compose`.

## Verificación adicional — caché de clientes

- Tests con monkeypatch: `python -m pytest tests/test_routes.py tests/test_processing.py -q` → 6 passed (1 warning deprecación Starlette/AnyIO).
- `ruff check .` → `All checks passed!`.
- `ruff format --check .` → `15 files already formatted`.
- `mypy app` → falló antes de iniciar: `error: uv trampoline failed to canonicalize script path`. Alternativa `python -m mypy app` → `Success: no issues found in 8 source files`.
- `pytest -q` → falló antes de iniciar con el mismo error del shim. Alternativa `python -m pytest -q` → `15 passed, 1 warning in 1.04s`.
