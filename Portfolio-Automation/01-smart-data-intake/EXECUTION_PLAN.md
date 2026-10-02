# Execution Plan — Smart Data Intake Pipeline

Source of truth: `README.md` (architecture, DB schema, API, docker services, file structure). This file is the atomic, checkable task list. Do not deviate from the README's architecture; this only sequences and verifies it.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (FastAPI, Pandas, Pydantic, Streamlit)
- `curl` for endpoint checks
- `redis-cli` and `psql` available (via `docker compose exec`) for verification steps

## Build Checklist

- [x] Create the empty file/dir tree from README section 7.
  - Done: backend/app and backend/tests listed; D1 defers frontend/ and n8n/ to items 8 and 9.
  - Verify: tree matches `backend/`, `frontend/`, `n8n/workflows/`, `docker-compose.yml`.
- [x] Write `docker-compose.yml` with only `postgres`, `redis`, `minio`.
  - Done: added Docker healthchecks (interval 10s, retries 10) for `minio` (`mc ready local`), `api` (`/health` via `urllib.request`), `dashboard` (`/_stcore/health` via `urllib.request`), and `n8n` (`wget -qO- /healthz`); `api` now `depends_on: minio` with `condition: service_healthy` and `dashboard` `depends_on: api` with `condition: service_healthy`. `docker compose --env-file .env.example up -d --wait` reports all 6 containers healthy.
  - Verify: `docker compose up -d postgres redis minio && docker compose ps` → all healthy.
- [x] Write `init-db.sql` with `uploads`, `clean_data`, `error_log` tables (README section 4). No Alembic.
  - Done: Postgres query listed exactly `clean_data`, `error_log`, `uploads`.
  - Verify: `docker compose exec postgres psql -U postgres -d intake_db -c '\dt'` lists 3 tables.
- [x] Implement Pydantic models in `backend/app/models.py`.
  - Done: `import app.models` succeeded; 2 model tests passed; ruff and mypy clean.
  - Verify: `python -c "import app.models"` succeeds.
- [x] Implement `clean_row()` in `backend/app/services.py` + `tests/test_services.py` using the 3 sample rows from README section 9.
  - Done: `pytest tests/test_services.py -v` returned 4 passed (three samples plus reasons); ruff and mypy clean.
  - Verify: `pytest tests/test_services.py -v` — 3/3 pass, correct classification each.
- [x] Implement `POST /api/v1/intake/upload` (MinIO upload + `uploads` insert + `BackgroundTasks` cleaning job, no Celery).
  - Done: smoke upload returned `status=processing`; both original objects were listed in MinIO by upload ID.
  - Verify: curl from README section 5 returns `"status": "processing"`; object visible in MinIO console.
- [x] Wire background task output: clean → `clean_data`, failed → `error_log`, ambiguous → Redis list `review_queue` (JSON).
  - Done: first smoke upload completed with 1 clean, 1 ambiguous in `review_queue`, and 1 failed row.
  - Verify: after uploading the sample CSV, `redis-cli LRANGE review_queue 0 -1` shows the ambiguous row.
- [x] Build `frontend/app.py` Streamlit dashboard (Approve/Reject on `review_queue`).
  - Done: dashboard approve moved the row into `clean_data`; reject moved it into `error_log`; both removed the item from Redis.
  - Verify: Approve removes the item from Redis and inserts it into `clean_data`.
- [ ] Build the 5-node n8n workflow (Webhook → HTTP Request → Wait → Split Out → Google Sheets), export JSON to `n8n/workflows/intake.json`.
  - Implemented; JSON validates and n8n `/healthz` returned HTTP 200. Verify pending: execute the webhook and confirm a Google Sheets row; credentials are not configured.
  - Verify: webhook trigger produces a new Google Sheets row.
- [x] Full stack up (`docker compose up -d`) + smoke test with the 3-row sample CSV.
  - Done: first upload completed with 1 row in `clean_data`, 1 in the dashboard queue, and 1 in `error_log`; source object verified in MinIO.
  - Verify: 1 row in `clean_data`, 1 in the dashboard queue, 1 in `error_log`.
- [x] Wire automated tests (unit → integration → E2E) per README section 11.
  - Done: added `backend/tests/test_integration_e2e.py`, marked `integration`/`e2e` (both registered in `pyproject.toml`, excluded from the default run via `addopts = "-ra -m \"not integration and not e2e\""` so the unit suite still runs without Docker). Tests hit the real stack (API `http://localhost:8001`, Postgres `localhost:5433`, Redis `localhost:6379`, MinIO `localhost:9000`), read connection settings from `E2E_*` env vars falling back to `.env.example` defaults, and `pytest.skip` cleanly when the stack is unreachable (verified against an unreachable port). The E2E test uploads `customers.csv`, polls `/api/v1/intake/{id}` until `completed`, asserts 1 clean / 1 ambiguous (review queue) / 1 failed for that upload, approves the ambiguous row via `POST .../review`, and asserts it moves to `clean_data`; a `finally` block deletes the `uploads` row (cascades to `clean_data`/`error_log`), removes any leftover `review_queue` entry, and removes the MinIO object. With the stack up: unit suite `21 passed`; integration+e2e suite `3 passed`. `ruff check`, `ruff format --check`, and `mypy app` are all clean.
  - Verify: full `pytest` suite green in CI.

## Definition of Done
- [x] `docker compose up -d` brings up all 6 services healthy.
- [x] `curl -X POST .../api/v1/intake/upload -F "file=@customers.csv"` (README section 5) returns `upload_id` and `"status": "processing"`.
- [x] The 3 sample rows from README section 9 land in the correct place (clean/ambiguous/failed) after one upload.
- [x] `pytest` (unit + integration + E2E) passes.
- [x] Streamlit dashboard can approve/reject a queued row and it moves to the correct table.

Google Sheets append remains unverified because n8n credentials are not configured.
