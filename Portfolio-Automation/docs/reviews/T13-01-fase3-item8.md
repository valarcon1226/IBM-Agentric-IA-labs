# T13-01 — Fase 3, ítem 8

- 8: `[ ]` dashboard Streamlit API-only: GET muestra filas y motivos; POST permite aprobar con correcciones opcionales o rechazar. `Authorization: Bearer` usa `API_KEY` de entorno; la clave no se muestra. Errores 401, 404, HTTP y conexión se presentan sin trazas.
- `frontend/requirements.txt`: `streamlit==1.54.0` (PyPI, 2026-02-04) y `httpx==0.28.1` (PyPI, 2024-12-06). Fuentes: https://pypi.org/project/streamlit/1.54.0/ y https://pypi.org/project/httpx/0.28.1/.
- `API_URL=http://api:8000` añadido a `.env.example`. El servicio `dashboard` se añadió a Compose porque README §6 lo enumera; no se agregó `depends_on: api` porque este Compose aún no define servicio `api`.
- Desde `01-smart-data-intake/`, `.\backend\.venv\Scripts\python.exe -m pytest frontend/tests -q` → 4 passed.
- `.\backend\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml frontend` → `All checks passed!`.
- `.\backend\.venv\Scripts\python.exe -m ruff format --check --config backend/pyproject.toml frontend` → `2 files already formatted`.
- `.\backend\.venv\Scripts\python.exe -m mypy --config-file backend/pyproject.toml frontend` → falló por detección duplicada de `app` y `frontend.app`. Mypy dirigido desde `frontend/`, `..\backend\.venv\Scripts\python.exe -m mypy --config-file ..\backend\pyproject.toml app.py` → `Success: no issues found in 1 source file`.
- Validación en Compose y acción real de Approve/Reject pendientes: needs Docker (D7). No se ejecutó ningún comando Docker.