# Execution Plan — Task Scheduler Engine

Source of truth: `README.md`. Note: use the `sqlalchemy-celery-beat` package (`DatabaseScheduler`) for DB-backed Beat scheduling — do not hand-roll a custom Beat `Scheduler` subclass, and do not use the abandoned `celery-sqlalchemy-scheduler` (last release 2021-04).

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`fastapi`, `celery`, `sqlalchemy-celery-beat`, `sqlalchemy`, `streamlit`)
- Build before this project: `03-multi-channel-notifier` (used for alerting on consecutive failures, per README section 2 features)

## Build Checklist

- [ ] Create the file/dir tree from README section 7; `docker-compose.yml` with `db` + `redis` only.
  - Verify: `docker compose up -d db redis` → healthy.
- [ ] Write init SQL for `tasks`, `task_runs`, `task_dependencies` (README section 4).
  - Verify: `\dt` lists all 3.
- [ ] Implement SQLAlchemy models mirroring the schema.
  - Verify: models import cleanly.
- [ ] Implement `executors/http_executor.py` + `executors/shell_executor.py` + `tests/test_executors.py` (mocked).
  - Verify: `pytest tests/test_executors.py -v` — success + failure/timeout cases pass.
- [ ] Configure `sqlalchemy-celery-beat`: `beat_dburi` = the PostgreSQL URL; Beat started with `-S sqlalchemy_celery_beat.schedulers:DatabaseScheduler`.
  - Verify: after Beat's first start, `\dt` shows the library's scheduler tables (periodic task, crontab/interval schedules) next to `tasks`.
- [ ] Sync each `tasks` row to exactly one `PeriodicTask` (`task-<task_id>`) in the same transaction as the API write (create / update / pause / delete).
  - Verify: creating a task via API creates one enabled `PeriodicTask`; pausing it sets `enabled = false`; deleting it removes it.
  - Verify: insert a task with `schedule="*/1 * * * *"`; a `task_runs` row appears within ~60s.
- [ ] Wire retry (`max_retries`/`retry_backoff`) and dependency-skip logic (`task_dependencies`).
  - Verify: task with unmet dependency is skipped and logged; task with met dependency runs.
- [ ] Implement the 4 API endpoints (README section 5).
  - Verify: each curl example returns the documented response; manual trigger creates an immediate `task_runs` row.
- [ ] Build the Streamlit dashboard (task list + run history).
  - Verify: a triggered run shows up in the dashboard.
- [ ] Full stack up + smoke test with the "Nightly Backup" example (short test schedule).
  - Verify: task executes, `task_runs` row has correct stdout/stderr and duration.

## Definition of Done
- [ ] `docker compose up -d` brings up `api`, `scheduler`, `worker`, `dashboard`, `db`, `redis` healthy.
- [ ] A task created via `POST /api/v1/tasks` runs on its schedule without restarting any service.
- [ ] Dependency-skip logic verified with a two-task chain (B depends on A).
- [ ] `pytest` full suite green.
