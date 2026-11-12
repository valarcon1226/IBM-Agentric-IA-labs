# Execution Plan — Multi-Channel Notification Hub

Source of truth: `README.md`. Note: broker standardized on **Redis** (not RabbitMQ) — do not add a `rabbitmq` service.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`fastapi`, `celery`, `jinja2`, `sqlalchemy`)
- SendGrid API key, Slack webhook URL, Telegram bot token (README section 10) — test/sandbox credentials are fine locally

## Build Checklist

- [x] Create the file/dir tree from README section 7; `docker-compose.yml` with `postgres` + `redis` only.
  - Verify: `docker compose up -d postgres redis` → healthy. (DECISIONES-03 N1/N4 amplía el compose:
    también `api`, `worker`, `mailpit` y `webhook-sink`, todos healthy — ver T-03-lote-a.md.)
- [x] Write `init-db.sql` for `templates`, `notifications`, `delivery_logs` (README section 4).
  - Verify: `\dt` lists all 3 tables. (DECISIONES-03 N2: sin tabla `templates`, solo `notifications`
    y `delivery_logs` — confirmado con `SELECT tablename FROM pg_tables`.)
- [x] Configure `app/workers/celery_app.py` with the Redis broker URL.
  - Verify: `celery -A app.workers.celery_app inspect ping` → `pong`.
- [x] Implement Jinja2 templates + `render_template()` + `tests/test_templates.py`.
  - Verify: `pytest tests/test_templates.py -v` passes.
- [x] Implement `email_task.py`, `slack_task.py`, Telegram task with `autoretry_for` + mocked tests.
  - Verify: `pytest tests/test_workers.py -v` — success path + retry-on-timeout path both pass.
    (DECISIONES-03 N7: retries use explicit `self.retry()` per attempt instead of the
    `autoretry_for` decorator param, so each attempt can be logged to `delivery_logs` before the
    retry/failure — Celery's backoff/jitter/max_retries mechanics are the same either way, see
    T-03-lote-b.md. Also added `discord_task.py`, `app/workers/common.py` and
    `app/notifications.py`, needed by this task and by the endpoints below.)
- [x] Implement `POST /api/v1/notify` (insert `notifications`, `.delay()` per channel, log to `delivery_logs`).
  - Verify: curl example from README section 5 returns `"status": "queued"`. (Uses
    `apply_async(priority=...)`, not `.delay()`, to carry the N7 priority mapping — see
    T-03-lote-b.md. Also implemented `GET /api/v1/notifications/{id}`, `GET /api/v1/notifications`
    and `GET /api/v1/templates`, Bearer-protected like `/notify`.)
- [x] Full stack up + smoke test with a multi-channel high-priority payload.
  - Verify: one `delivery_logs` row per requested channel. Confirmed with `["email", "slack"]`:
    2 `delivered` rows, `notifications.status = completed`, email visible in mailpit — see
    T-03-lote-b.md. Re-verified automatically against the live stack (not just a manual smoke
    test) by `tests/test_integration_e2e.py` (`integration`/`e2e` markers, excluded by default):
    2-channel (`email`+`slack`) and 4-channel (`email`+`slack`+`telegram`+`discord`) notifications
    both reach `completed` with one `delivered` `delivery_logs` row per channel, the email is
    visible in mailpit's API, and `GET /notifications/{id}` / `GET /notifications?status=completed`
    return the row — see T-03-lote-c.md.

## Definition of Done
- [x] `docker compose up -d` brings up `api`, `worker`, `postgres`, `redis` (no `rabbitmq`).
  - Verify: `worker` has `depends_on` `postgres` and `redis`, both with `condition: service_healthy` (it writes `delivery_logs`, so it needs the DB, not just the broker).
- [x] `curl -X POST .../api/v1/notify` (README section 5 payload) returns a `notification_id` and `"status": "queued"`.
- [x] Sending to `["email", "slack"]` produces exactly 2 `delivery_logs` rows.
- [x] A simulated SMTP timeout is retried by Celery (visible in worker logs) instead of failing immediately.
  - Verify: `tests/test_workers.py::test_email_timeout_retries` (mocked) plus a live demonstration
    in T-03-lote-c.md — `send_email_task.apply()` run eagerly against a closed local TCP port
    (`ConnectionRefusedError` → `TransientDeliveryError`), showing 5 real retries with growing,
    jittered countdowns (e.g. `0s`, `1s`, `3s`, `3s`, `11s`) before the final `failed` log, fixing
    the bug where manual `self.retry()` ignored `retry_backoff`/`retry_jitter`
    (`app.workers.common.retry_countdown`, DECISIONES-03 N7) — see T-03-lote-c.md.
- [x] `pytest` full suite green.
  - Unit suite (default, `integration`/`e2e` excluded): 83 passed. `integration`/`e2e` suite
    against the real docker compose stack: 3 passed (86 total) — see T-03-lote-c.md.
