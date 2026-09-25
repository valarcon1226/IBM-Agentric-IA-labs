# Execution Plan — Smart Data Intake Pipeline

Source of truth: `README.md` (architecture, DB schema, API, docker services, file structure). This file is the atomic, checkable task list. Do not deviate from the README's architecture; this only sequences and verifies it.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (FastAPI, Pandas, Pydantic, Streamlit)
- `curl` for endpoint checks
- `redis-cli` and `psql` available (via `docker compose exec`) for verification steps

## Build Checklist

- [ ] Create the empty file/dir tree from README section 7.
  - Verify: tree matches `backend/`, `frontend/`, `n8n/workflows/`, `docker-compose.yml`.
- [ ] Write `docker-compose.yml` with only `postgres`, `redis`, `minio`.
  - Verify: `docker compose up -d postgres redis minio && docker compose ps` → all healthy.
- [ ] Write `init-db.sql` with `uploads`, `clean_data`, `error_log` tables (README section 4). No Alembic.
  - Verify: `docker compose exec postgres psql -U postgres -d intake_db -c '\dt'` lists 3 tables.
- [ ] Implement Pydantic models in `backend/app/models.py`.
  - Verify: `python -c "import app.models"` succeeds.
- [ ] Implement `clean_row()` in `backend/app/services.py` + `tests/test_services.py` using the 3 sample rows from README section 9.
  - Verify: `pytest tests/test_services.py -v` — 3/3 pass, correct classification each.
- [ ] Implement `POST /api/v1/intake/upload` (MinIO upload + `uploads` insert + `BackgroundTasks` cleaning job, no Celery).
  - Verify: curl from README section 5 returns `"status": "processing"`; object visible in MinIO console.
- [ ] Wire background task output: clean → `clean_data`, failed → `error_log`, ambiguous → Redis list `review_queue` (JSON).
  - Verify: after uploading the sample CSV, `redis-cli LRANGE review_queue 0 -1` shows the ambiguous row.
- [ ] Build `frontend/app.py` Streamlit dashboard (Approve/Reject on `review_queue`).
  - Verify: Approve removes the item from Redis and inserts it into `clean_data`.
- [ ] Build the 4-node n8n workflow (Webhook → HTTP Request → Wait → Google Sheets), export JSON to `n8n/workflows/`.
  - Verify: webhook trigger produces a new Google Sheets row.
- [ ] Full stack up (`docker compose up -d`) + smoke test with the 3-row sample CSV.
  - Verify: 1 row in `clean_data`, 1 in the dashboard queue, 1 in `error_log`.
- [ ] Wire automated tests (unit → integration → E2E) per README section 11.
  - Verify: full `pytest` suite green in CI.

## Definition of Done
- [ ] `docker compose up -d` brings up all 6 services healthy.
- [ ] `curl -X POST .../api/v1/intake/upload -F "file=@customers.csv"` (README section 5) returns `upload_id` and `"status": "processing"`.
- [ ] The 3 sample rows from README section 9 land in the correct place (clean/ambiguous/failed) after one upload.
- [ ] `pytest` (unit + integration + E2E) passes.
- [ ] Streamlit dashboard can approve/reject a queued row and it moves to the correct table.
