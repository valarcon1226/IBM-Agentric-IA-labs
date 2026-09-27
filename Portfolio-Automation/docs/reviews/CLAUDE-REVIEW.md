# Revisión de Claude — ejecución paralela Gemini (04) + Copilot (01)

## DECISIÓN D1 — ubicación de la app del proyecto 01 (resuelve el bloqueo de `T13-01-fase2.md`)

Manda el README del proyecto: la API vive en **`01-smart-data-intake/backend/`**, igual que P10
(`10-docker-compose-lab/backend`, ya en CI con ese `project`).

- En T13, lee toda ruta del esqueleto (`app/`, `tests/`, `pyproject.toml`, `requirements*.txt`,
  `.env.example`, `.gitignore`, `Dockerfile`) como relativa a `01-smart-data-intake/backend/`.
  `app.main:app` se importa desde `backend/`, y las compuertas se corren desde `backend/`.
- `docker-compose.yml` e `init-db.sql` van en `01-smart-data-intake/` (raíz del proyecto), como en P10.
- `frontend/` y `n8n/`: fuera de la Fase 2. En la Fase 3, solo si un ítem del EXECUTION_PLAN los pide.
- No hace falta cambiar el README ni el EXECUTION_PLAN.

Copilot: retoma la Fase 2 con esta decisión y sigue con la Fase 3 según el prompt original.

## T01 (Gemini) — revisión 17:05, sin reporte todavía

- Los 3 archivos son idénticos al EXACTO. 29 passed, ruff check OK, mypy OK (25 archivos).
- **Defecto de la tarea, no de Gemini:** el EXACTO de `app/models/db.py` no pasa `ruff format --check`
  (línea 52, el `mapped_column(...)` de `status` cabe en 100 columnas). Arreglo permitido:
  `.venv\Scripts\ruff.exe format app\models\db.py` (solo formato). Reportarlo en "Desviaciones".
- **Falso positivo en la verificación 2:** `Column\(` coincide con `pa.Column(` de pandera en
  `app/api/routes/validate.py:20`, que no es SQLAlchemy. NO se toca `validate.py`: se reporta como
  falso positivo, y T01 cuenta como cumplida si la única coincidencia es `pa.Column`.
