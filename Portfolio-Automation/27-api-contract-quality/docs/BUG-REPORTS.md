# Bug Reports — Discovered During API Quality & Contract Verification

> **Note**: In accordance with the rules of the QA batch (`docs/tasks/_reglas-qa.md`), apps of other projects (13, 20, 22) are strictly **READ-ONLY**. These bugs were observed during live test execution and are fully documented here with exact steps and reproduction evidence without modifying the source repositories.

---

## BUG-P13-001: Project 13 Docker Container Fails to Start due to Hardcoded Relative Path to Widget

- **Component**: `13-whatsapp-restaurant-assistant/app/main.py:46-47`
- **Severity**: Critical (Deployment Blocker)
- **Status**: Open (Workaround applied via volume overlay in QA)
- **Date**: 2026-10-15

### Description

In `13-whatsapp-restaurant-assistant/app/main.py`, lines 46–47 mount the frontend widget:

```python
widget_dir = os.path.join(os.path.dirname(__file__), "..", "..", "22-web-chat-widget")
fastapi_app.mount("/widget", StaticFiles(directory=widget_dir, html=True), name="widget")
```

When running locally from a shell, `__file__` is inside the monorepo, so traversing two levels up reaches `Portfolio-Automation/22-web-chat-widget`.
However, inside the Docker image produced by `13-whatsapp-restaurant-assistant/Dockerfile`:

- `WORKDIR` is `/code`
- Only `COPY app ./app` and `COPY knowledge ./knowledge` are copied.
- `__file__` is `/code/app/main.py`.
- `os.path.abspath('/code/app/../../22-web-chat-widget')` evaluates to `/22-web-chat-widget`.

Because `/22-web-chat-widget` does not exist inside the container, Starlette's `StaticFiles` throws an immediate `RuntimeError`, causing Uvicorn to exit with code 1 and preventing the container from starting.

### Steps to Reproduce

1. In terminal, navigate to `13-whatsapp-restaurant-assistant/`.
2. Run `docker compose up --build`.
3. Observe `api` container status: `docker compose ps` shows `exited (1)`.
4. Inspect container logs: `docker logs 13-whatsapp-restaurant-assistant-api-1`.

### Evidence (Stack Trace)

```text
  File "/code/app/main.py", line 65, in <module>
    app = create_app(dev_mode=settings.DEV_MODE)
  File "/code/app/main.py", line 47, in create_app
    fastapi_app.mount("/widget", StaticFiles(directory=widget_dir, html=True), name="widget")
  File "/usr/local/lib/python3.12/site-packages/starlette/staticfiles.py", line 57, in __init__
    raise RuntimeError(f"Directory '{directory}' does not exist")
RuntimeError: Directory '/code/app/../../22-web-chat-widget' does not exist
```

### Proposed Fix for Project 13

Check `os.path.exists(widget_dir)` before mounting, or provide a configurable environment variable `WIDGET_STATIC_DIR` with fallback:

```python
if os.path.isdir(widget_dir):
    fastapi_app.mount("/widget", StaticFiles(directory=widget_dir, html=True), name="widget")
```

---

## BUG-P13-002: Unhandled 500 DBAPIError in `/web/chat` When `session_id` Exceeds 16 Characters

- **Component**: `13-whatsapp-restaurant-assistant/app/web_chat.py:13,36` vs `init-db.sql: customers(wa_id VARCHAR(20))`
- **Severity**: High (Unhandled 500 Server Error)
- **Status**: Open
- **Date**: 2026-10-15

### Description

In `13-whatsapp-restaurant-assistant/app/web_chat.py`, the Pydantic schema declares:

```python
class WebChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=1000)
```

The endpoint then constructs:

```python
wa_id = f"web_{request.session_id}"
replies = await process_incoming_message(wa_id, None, "text", request.text)
```

In `13-whatsapp-restaurant-assistant/app/conversation.py`, `process_incoming_message` inserts into the `customers` table:

```sql
INSERT INTO customers (wa_id) VALUES (:wa_id) ON CONFLICT (wa_id) DO NOTHING
```

However, in `init-db.sql`, `customers.wa_id` is typed as `VARCHAR(20)`.
Because `web_` uses 4 characters, any valid `session_id` between 17 and 100 characters produces a `wa_id` between 21 and 104 characters.
PostgreSQL rejects the insert with `sqlalchemy.exc.DBAPIError: value too long for type character varying(20)`, returning a 500 Internal Server Error instead of 200 or 422.

### Steps to Reproduce

1. Start Project 13 backend.
2. Send a POST request to `/web/chat` with a 17-character `session_id`:

```bash
curl -X POST http://127.0.0.1:8004/web/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "session-flooder-999", "text": "Hello"}'
```

3. Observe HTTP 500 response.

### Evidence (Container Log)

```text
sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) value too long for type character varying(20)
[SQL: INSERT INTO customers (wa_id) VALUES ($1) ON CONFLICT (wa_id) DO NOTHING]
[parameters: ('web_session-flooder-999',)]
(Background on this error at: https://sqlalche.me/e/21/dbapi)
```

### Proposed Fix for Project 13

Alter the database column `customers.wa_id` to `VARCHAR(128)` to accommodate `web_` prefix + up to 100 characters of `session_id`, or restrict `WebChatRequest.session_id` to `max_length=16`.

---

## BUG-P20-001: 7 Schema Conformance Violations Discovered by Schemathesis in Project 20 OpenAPI

- **Component**: `20-ecommerce-order-automation/app/main.py`
- **Severity**: Medium (API Contract & Specification Drift)
- **Status**: Open
- **Date**: 2026-10-15

### Description

Property-based fuzzing with Schemathesis against `http://127.0.0.1:8000/openapi.json` executed 171 test cases across all 12 API operations, identifying 7 unique contract non-conformance defects:

1. **Undocumented Content-Type in `GET /admin/logout`**:
   - Received: `text/html; charset=utf-8` (renders HTML login box).
   - Documented in OpenAPI: `application/json`.
   - Curl to reproduce: `curl -X GET http://127.0.0.1:8000/admin/logout`

2. **Undocumented Content-Type in `GET /admin/orders/export`**:
   - Received: `text/html; charset=utf-8` (unauthenticated requests render login page).
   - Documented in OpenAPI: `application/json`.
   - Curl to reproduce: `curl -X GET 'http://127.0.0.1:8000/admin/orders/export'`

3. **Undocumented Content-Type in `POST /admin/orders/{order_id}/status`**:
   - Received: `text/html; charset=utf-8` on unauthenticated requests.
   - Documented in OpenAPI: `application/json`.
   - Curl to reproduce: `curl -X POST http://127.0.0.1:8000/admin/orders/1/status`

4. **Undocumented HTTP Status Code in `POST /admin/login`**:
   - Received: `400 Bad Request` with HTML response.
   - Documented in OpenAPI: only `200` and `422`.
   - Curl to reproduce: `curl -X POST -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=&password=&csrf_token=' http://127.0.0.1:8000/admin/login`

5. **Undocumented HTTP Status Code in `POST /webhooks/shopify`**:
   - Received: `401 Unauthorized` (`{"detail":"Firma de webhook Shopify inválida (x-shopify-hmac-sha256)."}`).
   - Documented in OpenAPI: only `200` and `422`. Missing documented 401 response.
   - Curl to reproduce: `curl -X POST http://127.0.0.1:8000/webhooks/shopify`

6. **Undocumented HTTP Status Code in `POST /webhooks/stripe`**:
   - Received: `400 Bad Request` (`{"detail":"Firma de Stripe inválida o fuera de tolerancia: Firma o secreto no suministrado"}`).
   - Documented in OpenAPI: only `200` and `422`. Missing documented 400 response.
   - Curl to reproduce: `curl -X POST http://127.0.0.1:8000/webhooks/stripe`

7. **Undocumented HTTP Status Code in `POST /webhooks/woocommerce`**:
   - Received: `401 Unauthorized` (`{"detail":"Firma de webhook WooCommerce inválida (x-wc-webhook-signature)."}`).
   - Documented in OpenAPI: only `200` and `422`. Missing documented 401 response.
   - Curl to reproduce: `curl -X POST http://127.0.0.1:8000/webhooks/woocommerce`

### Proposed Fix for Project 20

1. Add `response_class=HTMLResponse` to all FastAPI HTML template endpoints (`/admin/login`, `/admin/logout`, etc.).
2. Declare explicit `responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}}` in webhook route decorators.
