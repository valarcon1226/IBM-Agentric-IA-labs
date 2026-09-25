# Project: Multi-Channel Notification Hub

## 1. Problem Statement
Microservices and automated pipelines often need to notify users. Instead of duplicating SMTP settings, Slack webhooks, Discord hooks, and Telegram API keys across every single project, this centralized service handles all outbound communications. It ensures delivery, templates messages, manages rate limits, and provides a unified audit log.

## 2. Architecture

```mermaid
flowchart TD
    A[Any Client / App] -->|POST /notify| B(FastAPI Gateway)
    B -->|Save to DB| C[(PostgreSQL)]
    B -->|Publish Event| D((Redis))
    D --> E[Celery Worker: Email]
    D --> F[Celery Worker: Slack]
    D --> G[Celery Worker: Telegram]
    D --> H[Celery Worker: Discord]
    E --> I[SendGrid / SMTP]
    F --> J[Slack API]
    G --> K[Telegram API]
    H --> L[Discord API]
```

## 3. Tech Stack
- **API Gateway:** FastAPI
- **Message Queue:** Redis (Celery broker — chosen over RabbitMQ because Redis is already required infra in other parts of this portfolio, avoiding a brand-new service)
- **Async Workers:** Celery
- **Templating:** Jinja2
- **Database:** PostgreSQL
- **Infrastructure:** Docker Compose

## 4. Database Schema

*Note: Templates are loaded from the filesystem (`app/templates/*.j2`) on startup. The application code validates that `template_name` matches an existing file before accepting a request.*

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(100) NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'queued',
    recipients JSONB NOT NULL,
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE delivery_logs (
    log_id SERIAL PRIMARY KEY,
    notification_id UUID REFERENCES notifications(id) ON DELETE CASCADE,
    channel VARCHAR(50),
    status VARCHAR(50),
    error_message TEXT,
    attempt_number INT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 5. API Endpoints

### Send Notification
**POST /api/v1/notify**

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/notify" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "welcome_email",
    "channels": ["email", "slack", "telegram", "discord"],
    "priority": "high",
    "recipients": {
      "email": ["alice@example.com"],
      "slack": ["#alerts"],
      "telegram": ["123456789"],
      "discord": ["1020304050"]
    },
    "payload": {
      "user_name": "Alice",
      "system": "Data Intake Pipeline"
    }
  }'
```

**Response:**
```json
{
  "notification_id": "987e6543-e21b-34d3-b456-426614174111",
  "status": "queued",
  "message": "Notification queued for processing."
}
```

### Check Delivery Status
**GET /api/v1/notifications/{id}**

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/notifications/987e6543-e21b-34d3-b456-426614174111"
```

**Response:**
```json
{
  "id": "987e6543-e21b-34d3-b456-426614174111",
  "template_name": "welcome_email",
  "status": "completed",
  "created_at": "2024-01-01T12:00:00Z",
  "delivery_logs": [
    {
      "channel": "email",
      "status": "delivered",
      "processed_at": "2024-01-01T12:00:05Z"
    },
    {
      "channel": "slack",
      "status": "delivered",
      "processed_at": "2024-01-01T12:00:02Z"
    }
  ]
}
```

### List Notifications
**GET /api/v1/notifications?status=failed&since=2024-01-01**

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/notifications?status=failed&since=2024-01-01"
```

**Response:**
```json
{
  "results": [
    {
      "id": "111e6543-e21b-34d3-b456-426614174222",
      "template_name": "alert_critical",
      "status": "failed",
      "created_at": "2024-01-02T15:30:00Z"
    }
  ],
  "total": 1
}
```

### List Available Templates
**GET /api/v1/templates**

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/templates"
```

**Response:**
```json
{
  "templates": [
    "welcome_email",
    "slack_alert",
    "daily_report"
  ]
}
```

## 6. Docker Services

| Service | Image/Dockerfile | Ports | Depends On |
|---------|------------------|-------|------------|
| `api` | `Dockerfile` | 8000:8000 | `postgres`, `redis` |
| `worker` | `Dockerfile` | - | `api`, `redis` |
| `postgres` | `postgres:15-alpine`| 5432:5432 | - |
| `redis` | `redis:7-alpine` | 6379:6379 | - |

## 7. File Structure
```text
03-multi-channel-notifier/
├── app/
│   ├── main.py
│   ├── templates/
│   │   ├── slack_alert.j2
│   │   └── welcome_email.html.j2
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── email_task.py
│   │   ├── slack_task.py
│   │   ├── telegram_task.py
│   │   └── discord_task.py
│   ├── models.py
│   └── database.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## 8. Implementation Steps
1. **Repo skeleton + infra** — create the tree from section 7; `docker-compose.yml` with `postgres` and `redis` only (worker/api added once their code exists). *Verify:* `docker compose up -d postgres redis` → healthy.
2. **Schema via plain SQL** — write `init-db.sql` for `notifications` and `delivery_logs` from section 4. *Verify:* `\dt` lists both tables.
3. **Celery + Redis broker** — configure `app/workers/celery_app.py` with `CELERY_BROKER_URL=redis://redis:6379/0`. *Verify:* `celery -A app.workers.celery_app inspect ping` returns `pong`.
4. **Jinja2 templates, tested standalone** — implement `app/templates/*.j2` and a `render_template(name, context) -> str` helper; write `tests/test_templates.py`. *Verify:* `pytest tests/test_templates.py -v` passes for `welcome_email` and `slack_alert`. Template validation happens on load without DB queries.
5. **Channel tasks** — implement `email_task.py` (SMTP), `slack_task.py`, `telegram_task.py`, and `discord_task.py`, each wrapped with Celery's built-in `autoretry_for` + exponential backoff for transient network errors. Mock the external clients in `tests/test_workers.py`. *Verify:* mocked tests confirm each task calls its respective external client exactly once on success, and retries on a simulated timeout.
6. **API endpoints** — implement the endpoints detailed in section 5 in `app/main.py`: `POST /notify` (insert a row, then `.delay()` one Celery task per requested channel, writing a `delivery_logs` row per attempt), `GET /notifications/{id}`, `GET /notifications`, and `GET /templates`. *Verify:* the curl examples in section 5 return the expected JSON structures, and the Celery worker log shows one task per channel for `/notify`.
7. **Full stack + smoke test** — `docker compose up -d`, send a `high` priority notification with `channels: ["email", "slack"]`, confirm two `delivery_logs` rows are created (one per channel).

## 9. Testing Strategy
1. **Unit tests (step 4):** Jinja2 template rendering, checking disk load, no DB I/O.
2. **Worker tests (step 5):** mock SendGrid/Slack/Telegram/Discord clients, assert each Celery task fires correctly and retries on transient failure.
3. **E2E test (step 6-7):** POST a multi-channel high-priority payload and assert tasks are enqueued for every requested channel simultaneously, with a `delivery_logs` row per channel. Test query endpoints for correct aggregation.

## 10. Environment Variables
```env
DATABASE_URL=postgresql://postgres:secret@postgres:5432/notifier_db
CELERY_BROKER_URL=redis://redis:6379/0
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_key
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
TELEGRAM_BOT_TOKEN=your_telegram_token
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

