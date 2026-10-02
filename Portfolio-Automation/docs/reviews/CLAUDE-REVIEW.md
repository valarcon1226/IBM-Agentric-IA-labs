# Revisión de Claude — ejecución paralela Gemini (04) + Copilot (01)

> **Actualización 2026-09-27:** todas las decisiones del proyecto 01 están ahora en
> [`DECISIONES-01.md`](DECISIONES-01.md). T01 cerrada por Claude (commit `1ff0142`).

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

## Ensayo previo de T02–T06 (2026-09-27, Claude)

Claude aplicó el código EXACTO de T02–T06 en un worktree aparte y corrió las compuertas antes de
dárselas a Gemini: T02 29 · T03 31 · T04 34 · T05 38 · T06 38 passed + 2 deselected (integración:
2 skipped sin Docker). Defectos corregidos en las tareas:
- `Select-String -Recurse` no existe en PowerShell 5.1 → `Get-ChildItem ... | Select-String` (T01, T04, T05, T07, T08).
- EXACTO sin formato ruff → corregido (T01 `db.py`, T04 `process_enrich_job`).
- T06 Paso 6 insertaba en el CI un paso que T12 ya agregó → ahora solo se verifica que exista.

## Proyecto 01 — revisión Fase 2 + ítems 1–3 (Copilot, 2026-09-27)

Bien: estructura D1, settings requeridas sin defecto, `.env.example` con `change_me_*`, auth Bearer
copiada de 04, `/health` 503, gates verdes salvo el rojo esperado de rutas. Corregido por Claude:
- Faltaba `01-smart-data-intake/.gitignore`: un `.env` en la raíz del proyecto se habría
  commiteado (repo público). Agregado con `.env`.
- El compose no tenía healthchecks, así que el Verify del ítem 2 ("all healthy") nunca podía
  pasar. Agregados: `pg_isready`, `redis-cli ping`, `mc ready local` (lección DL-R06/R07 de P10).
Pendiente de revisar en la Fase 3: las 4 rutas deben llevar `Depends(verify_api_key)`.

## Proyecto 01 — revisión ítems 4–6 (+ ítem 7 en curso)

Bien: las 4 rutas bajo `APIRouter(dependencies=[Depends(verify_api_key)])`; SQL siempre con
parámetros; las 3 filas del README §9 dan clean/ambiguous/failed; duplicados → `error_log`;
el callback a n8n no tumba el job; 14 tests en verde (el test de rutas ya pasa).
Para corregir antes del commit (no bloquean a Copilot):
- `normalize_row` no garantiza las 5 columnas: un CSV sin la columna `company` (o con otro
  encabezado) hace fallar `insert_clean` con KeyError y marca TODO el upload como `failed`.
  Arreglo: normalizar solo `first_name, last_name, email, phone, company` con `""` por defecto.
- Al momento de la revisión: `ruff check` 14 errores y 3 archivos sin formato (trabajo en curso);
  revisar que queden en verde al cerrar el ítem 7.
