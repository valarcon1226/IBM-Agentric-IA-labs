# Decisiones para construir `01-smart-data-intake` (T13, Fases 2–3)

Escritas por Claude **antes** de la ejecución, para que el agente no tenga que detenerse por
ambigüedades. Si algo no está aquí y bloquea, se detiene; si no bloquea, elige lo más simple,
lo anota en el reporte y sigue. Estas decisiones mandan sobre T13 cuando lo contradigan.

## D1 — Estructura: la del README, no la de 04

- Todo el código Python vive en `01-smart-data-intake/backend/`. Compuertas, venv y tests se
  corren **desde `backend/`** (como `10-docker-compose-lab/backend`).
- Módulos planos, como dice el README §7: `backend/app/{__init__,main,models,routes,services,config}.py`.
  Agrega solo `backend/app/security.py` (D4) y `backend/app/db.py` (conexión). **No** crees
  `api/routes/`, `core/`, `models/`, `services/` como carpetas.
- `backend/tests/`, `backend/pyproject.toml`, `backend/requirements*.txt`, `backend/.env.example`,
  `backend/.gitignore` (copia el de 04), `backend/Dockerfile`.
- En la raíz del proyecto: `docker-compose.yml`, `init-db.sql`, `.env.example` (para el compose).
- `frontend/` y `n8n/` solo cuando llegue su ítem del EXECUTION_PLAN.

## D2 — Versiones

- Python **3.12** (no 3.11): igual que 04 y P10. `requires-python = ">=3.12"`.
- Herramientas de dev: las mismas versiones que `04-data-cleaning-api/requirements-dev.txt`
  (+ `testcontainers[postgres]==4.15.0` para integración).
- Imagen de Postgres: `postgres:15-alpine`, como dice el README §6.
- Librerías nuevas: versión fija de PyPI, anotada en el reporte con su fecha de release.

## D3 — Configuración y secretos (lecciones de T11/T12)

- `config.py` con pydantic-settings. Requeridas y **sin valor por defecto**: `DATABASE_URL`,
  `REDIS_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `API_KEY`.
  Con defecto: `MINIO_BUCKET_NAME="intake-files"`, `N8N_CALLBACK_URL: str | None = None`.
- `.env.example` usa `change_me_<nombre>` como valor de las contraseñas (nunca `secret` ni
  `password`). `.env` va en `.gitignore`. Ningún secreto real en archivos versionados.
- El compose toma todo de `${VAR}` (edita con las herramientas del editor, nunca con strings
  de PowerShell: ver copilot-instructions).

## D4 — Autenticación: sí, igual que 04

- La API usa `verify_api_key` de 04 (Bearer token, `secrets.compare_digest`) en todas las rutas
  menos `/health`.
- Actualiza los 4 `curl` del README §5 agregando `-H "Authorization: Bearer $API_KEY"` y agrega
  `API_KEY=change_me_api_key` al README §12. Es el único cambio permitido al README.
- El dashboard de Streamlit manda el mismo header.

## D5 — Reglas de limpieza (`services.py`)

- Mantén la firma del README: `clean_row(row: dict) -> Literal["clean", "ambiguous", "failed"]`.
- Agrega `row_issues(row: dict) -> list[str]`, y que `clean_row` se derive de ella. Así la ruta de
  revisión puede devolver `reasons`.
- Normalización: `strip()` en todo; `email` en minúsculas.
- **failed** si falta `first_name` o `last_name`, o si el email no tiene forma `algo@algo`.
  Motivo: `"Missing required fields"` o `"Invalid email"`.
- **ambiguous** (si no es failed) si falta `company` (`"Missing company"`), si el dominio del
  email no tiene punto (`"Potentially invalid email domain"`), o si el teléfono no coincide
  con `^\+?[\d\s\-().]{7,}$` (`"Invalid phone"`).
- Si no, **clean**. Las 3 filas del README §9 deben dar clean / ambiguous / failed.
- Email duplicado dentro del mismo upload (`UNIQUE(upload_id, email)`): la segunda fila va a
  `error_log` con `"Duplicate email in upload"`. Nunca dejes que la excepción tumbe el job.

## D6 — Cola de revisión y callbacks

- Cada fila ambigua se guarda en la lista Redis `review_queue` como JSON con
  `record_id` (uuid4 nuevo), `upload_id`, `line_number`, `data` y `reasons`.
- `GET /{upload_id}/review` filtra la lista por `upload_id`. `POST /{upload_id}/review`
  busca por `record_id`: approve → inserta `corrected_data` (o `data`) en `clean_data`;
  reject → inserta en `error_log` con `"Rejected in review"`. Después `LREM` exacto del JSON
  original. `record_id` inexistente → 404.
- `GET /{upload_id}`: `clean_rows` = COUNT en `clean_data`, `failed_rows` = COUNT en `error_log`,
  `ambiguous_rows` = items del upload en `review_queue`. Upload inexistente → 404.
- Al terminar el job: `uploads.status = 'completed'` (o `'failed'` si explota) y
  `total_rows`. Si `N8N_CALLBACK_URL` está definido, POST con `upload_id` y los conteos;
  si falla, se registra en el log y **no** marca el upload como fallido.

## D7 — Docker apagado, Google Sheets sin credenciales

El daemon de Docker no está disponible en esta máquina. Para los ítems cuyo `Verify:` necesita
Docker (`docker compose up`, `psql`, consola MinIO, `redis-cli`) o Google Sheets:

1. Escribe el artefacto igual.
2. Verifica lo que se pueda sin Docker: `docker compose config -q` **y** revisa el valor
   resuelto (no solo que no dé error); JSON válido; los tests unitarios con fakes.
3. Deja el ítem en `- [ ]` con la línea `  - Written; Verify pending: needs Docker` (o
   `needs Google credentials`) y **sigue con el siguiente ítem**. No lo marques `[x]`.

Tests de integración: patrón de `docs/tasks/T06-tests-integracion-postgres.md` (testcontainers,
marcador `integration`, se saltan con "Docker not available"). No necesitas que T06 esté hecha:
copia el patrón del archivo de la tarea. `jobs_repo` de 04 **no** aplica a este proyecto.

## D8 — Qué no hacer

- No hagas la Fase 4 (CI, README raíz, RISK-ANALYSIS): la hace Claude.
- No agregues Celery, Alembic, ni carpetas que el README no pida.
- `frontend/`: solo `ruff check` y `ruff format`; sin tests de UI.
