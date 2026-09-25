# Execution Plan — Multi-Channel Notification Hub

Source of truth: `README.md`. Note: broker standardized on **Redis** (not RabbitMQ) — do not add a `rabbitmq` service.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`fastapi`, `celery`, `jinja2`, `sqlalchemy`)
- SendGrid API key, Slack webhook URL, Telegram bot token (README section 10) — test/sandbox credentials are fine locally

## Build Checklist

- [ ] Create the file/dir tree from README section 7; `docker-compose.yml` with `postgres` + `redis` only.
  - Verify: `docker compose up -d postgres redis` → healthy.
- [ ] Write `init-db.sql` for `templates`, `notifications`, `delivery_logs` (README section 4).
  - Verify: `\dt` lists all 3 tables.
- [ ] Configure `app/workers/celery_app.py` with the Redis broker URL.
  - Verify: `celery -A app.workers.celery_app inspect ping` → `pong`.
- [ ] Implement Jinja2 templates + `render_template()` + `tests/test_templates.py`.
  - Verify: `pytest tests/test_templates.py -v` passes.
- [ ] Implement `email_task.py`, `slack_task.py`, Telegram task with `autoretry_for` + mocked tests.
  - Verify: `pytest tests/test_workers.py -v` — success path + retry-on-timeout path both pass.
- [ ] Implement `POST /api/v1/notify` (insert `notifications`, `.delay()` per channel, log to `delivery_logs`).
  - Verify: curl example from README section 5 returns `"status": "queued"`.
- [ ] Full stack up + smoke test with a multi-channel high-priority payload.
  - Verify: one `delivery_logs` row per requested channel.

## Definition of Done
- [ ] `docker compose up -d` brings up `api`, `worker`, `postgres`, `redis` (no `rabbitmq`).
  - Verify: `worker` has `depends_on` `postgres` and `redis`, both with `condition: service_healthy` (it writes `delivery_logs`, so it needs the DB, not just the broker).
- [ ] `curl -X POST .../api/v1/notify` (README section 5 payload) returns a `notification_id` and `"status": "queued"`.
- [ ] Sending to `["email", "slack"]` produces exactly 2 `delivery_logs` rows.
- [ ] A simulated SMTP timeout is retried by Celery (visible in worker logs) instead of failing immediately.
- [ ] `pytest` full suite green.
