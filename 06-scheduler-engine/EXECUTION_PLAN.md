# Execution Plan — Task Scheduler Engine

Source of truth: `README.md`. Uses `sqlalchemy-celery-beat` (`DatabaseScheduler`) for DB-backed Celery Beat scheduling.

## Prerequisites
- Docker + Docker Compose
- Python 3.12 (`fastapi`, `celery`, `sqlalchemy-celery-beat`, `sqlalchemy`, `streamlit`, `httpx`)
- Webhook sink (`mendhak/http-https-echo:36`) or `03-multi-channel-notifier` for alerts

## Build Checklist

- [x] Create the file/dir tree from README section 9; `docker-compose.yml` with all services (`api`, `scheduler`, `worker`, `dashboard`, `db`, `redis`, `webhook-sink`).
- [x] Write init SQL for `tasks`, `task_runs`, `task_dependencies` (`init-db.sql`).
- [x] Implement SQLAlchemy models mirroring the schema (`app/models/database.py`).
- [x] Implement executors (`http_executor.py`, `shell_executor.py`, `python_executor.py`) with whitelist, SSRF protection, no `shell=True`, no `eval`.
- [x] Configure `sqlalchemy-celery-beat`: `beat_dburi` pointing to PostgreSQL URL; Beat started with `-S sqlalchemy_celery_beat.schedulers:DatabaseScheduler`.
- [x] Sync each `tasks` row to exactly one `PeriodicTask` (`task-<task_id>`) in the same transaction as API write (create / update / pause / delete) and trigger `PeriodicTaskChanged`.
- [x] Wire retry (`max_retries`/`retry_backoff`), dependency-skip logic (`task_dependencies`), and webhook alerting upon consecutive failures.
- [x] Implement FastAPI CRUD routes, manual trigger, and run history.
- [x] Build Streamlit dashboard (`dashboard/app.py`) communicating solely with API.
- [x] Comprehensive test suite (unit tests + integration tests) with 25 unit tests passing.

## Definition of Done
- [x] `docker compose up -d --build` brings up `api` (port 8006), `dashboard` (port 8506), `scheduler`, `worker`, `db`, `redis`, `webhook-sink`.
- [x] A task created via `POST /api/v1/tasks` runs on schedule without restarting any service.
- [x] Dependency-skip logic verified with a two-task chain (B depends on A).
- [x] Consecutive failures trigger webhook alert to sink.
- [x] `pytest` full suite green.
