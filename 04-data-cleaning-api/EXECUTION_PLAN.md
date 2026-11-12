# Execution Plan — Data Cleaning & Transformation API

Source of truth: `README.md`. Note: build with **Pandas only** first — do not add Polars unless a specific endpoint is profiled and shown too slow.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`fastapi`, `pandas`, `pandera`, `celery`, `httpx` for tests)

## Build Checklist

- [ ] Create the file/dir tree from README section 7.
  - Verify: matches `app/api/routes/`, `app/core/`, `app/services/`, `tests/`.
- [ ] `docker-compose.yml` with `db`, `redis`, `minio` only.
  - Verify: `docker compose up -d db redis minio` → healthy.
- [ ] Write init SQL for `schemas` and `jobs` tables (README section 4).
  - Verify: `\dt` lists both.
- [ ] Implement `services/cleaner.py` (Pandas) + `tests/test_cleaner.py` on a fixture DataFrame.
  - Verify: `pytest tests/test_cleaner.py -v` passes.
- [ ] Implement Pandera schemas + `POST /api/v1/validate`.
  - Verify: curl example from README section 5.2 returns correct pass/fail.
- [ ] Configure `core/worker.py` (Celery + Redis) and size-based sync/async routing in `POST /api/v1/clean`.
  - Verify: small file → inline result; large file → `job_id` + `GET /api/v1/jobs/{job_id}` shows status transitions.
- [ ] Implement `services/storage.py` (MinIO) wired to `jobs.input_file_path`/`output_file_path`.
  - Verify: after a job completes, both MinIO objects exist and the DB row references them.
- [ ] Wire `transform`, `enrich`, `upload`, `jobs/{id}/result` endpoints.
  - Verify: each curl example in README section 5 returns its documented shape.
- [ ] Full stack up + smoke test with `dirty.csv` (`remove_duplicates: true`).
  - Verify: output has no duplicate rows.

## Definition of Done
- [ ] `docker compose up -d` brings up `api`, `worker`, `db`, `redis`, `minio` healthy.
- [ ] `curl -X POST .../api/v1/clean -F "file=@dirty.csv" ...` (README 5.1) returns a valid `job_id`.
- [ ] `pytest` (cleaner unit tests + validation tests + upload/MinIO integration test) passes.
- [ ] No Polars dependency present unless explicitly added later with a documented profiling reason.
