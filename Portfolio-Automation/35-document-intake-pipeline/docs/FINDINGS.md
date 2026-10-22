# Findings: Document Intake Pipeline (Paperless-ngx)

This document tracks defects, unexpected behaviors, and target deviations identified in the system under test (Paperless-ngx 2.14.7).

---

## FINDING-001: Critical Accessibility Violations in Upstream Angular Web UI

- **Component:** Upstream Angular SPA (`src-ui/src/app/components/document-list/`)
- **SUT Version:** `ghcr.io/paperless-ngx/paperless-ngx:2.14.7`
- **Severity:** High (Accessibility / Compliance)
- **Target:** `a11y_violations_critical_count = 0` (in `targets.toml`)
- **Measured Result:** 6 critical/serious violations (`a11y_violations_critical_count = 6`)
- **Status:** Documented, marked `xfail(strict=True, reason="FINDING-001")` per measurement rules. SUT remains unpatched.

### Reproduction Steps
1. Deploy Paperless-ngx stack 2.14.7.
2. Ingest documents and navigate to `/documents` in Microsoft Edge or Firefox.
3. Inject axe-core 4.10.2 via Playwright `page.evaluate(axe_script)`.
4. Run `axe.run()` on the active DOM.

### Expected Result
Zero critical or serious accessibility violations (`impact in ("critical", "serious")`).

### Actual Result
axe-core detected 6 critical and serious accessibility violations in the documents table and filter bar components:
1. `[CRITICAL] aria-allowed-attr`: Elements must only use allowed ARIA attributes.
2. `[CRITICAL] aria-required-children`: Certain ARIA roles (`role="menubar"`, `role="listbox"`) must contain required children.
3. `[CRITICAL] aria-valid-attr-value`: ARIA attributes must conform to valid values.
4. `[CRITICAL] button-name`: Icon buttons in the toolbar lack discernible text or `aria-label`.
5. `[CRITICAL] label`: Form `<select>` and `<input>` filter controls lack explicit `<label>` or `aria-label`.
6. `[SERIOUS] link-name`: Pagination navigation links lack accessible names.
7. `[SERIOUS] listitem`: `<li>` elements inside dynamic filter menus are not properly contained in `<ul>` or `<ol>`.

### Evidence
Axe audit report output from `test_document_flow.py`:
```text
[A11Y AUDIT] Axe-core scanned /documents: 10 total violations, 6 critical/serious violations.
  - [CRITICAL] aria-allowed-attr: Elements must only use allowed ARIA attributes
  - [CRITICAL] aria-required-children: Certain ARIA roles must contain particular children
  - [CRITICAL] aria-valid-attr-value: ARIA attributes must conform to valid values
  - [CRITICAL] button-name: Buttons must have discernible text
  - [CRITICAL] label: Form <select> and <input> elements must have labels
  - [SERIOUS] link-name: Links must have discernible text
  - [SERIOUS] listitem: <li> elements must be contained in a <ul> or <ol>
```

---

## FINDING-002: Encrypted PDF Behavior Defaults to Non-Destructive Ingest with Skipped OCR

- **Component:** Celery Consumer (`src/documents/consumer.py`)
- **SUT Version:** `ghcr.io/paperless-ngx/paperless-ngx:2.14.7`
- **Severity:** Low (Architectural Decision)
- **Status:** Documented & Verified.

### Observation
When ingesting an encrypted / password-protected PDF, Paperless-ngx does not fail the Celery task with `FAILURE`. Instead, it completes with `SUCCESS`, preserving the encrypted original file in media storage and skipping OCR with a log entry `Document is password protected, skipping OCR`. This behavior is intentionally designed in Paperless-ngx to enable delayed administrative decryption via `python3 manage.py decrypt_documents`. The API returns HTTP 200 and the consumer never hangs or crashes.

---

## FINDING-003: Unacknowledged Tasks Remain Stuck in PENDING After Abrupt Redis Restart

- **Component:** Celery Broker / Kombu Redis Transport (`paperless-webserver` & `paperless-redis`)
- **SUT Version:** `ghcr.io/paperless-ngx/paperless-ngx:2.14.7`
- **Severity:** Medium (Resilience / Broker Reconnection)
- **Target:** `tasks_stuck_after_fault = 0` (in `targets.toml`)
- **Status:** Documented, marked `xfail(strict=True, reason="FINDING-003")` per measurement rules. SUT remains unpatched.

### Reproduction Steps
1. Start an asynchronous burst of 100 documents (`POST /api/documents/post_document/`).
2. Monitor `/api/tasks/` until at least 30 tasks reach a terminal state (`SUCCESS`).
3. While the remaining 70 tasks are actively draining, restart the Redis broker (`docker compose restart redis`).
4. Wait for Celery worker to reconnect (`Connected to redis://toxiproxy:6379//`).
5. Poll `/api/tasks/` for completion of all 100 tasks.

### Expected Result
All 100 tasks reach terminal states (`SUCCESS` or `FAILURE` with reason), and 0 tasks remain stuck in `PENDING` or `STARTED`.

### Actual Result
When Redis is abruptly restarted, in-flight prefetched tasks (8 tasks, matching Kombu's `worker_prefetch_multiplier = 4` across 2 worker processes) are stored in Kombu's `unacked` hash in Redis. Upon reconnecting, the active Celery worker does not re-process or redeliver these tasks because Kombu's Redis transport defaults to a 3,600-second (1 hour) `visibility_timeout`. Consequently, 8 tasks remain permanently stuck in `PENDING` in the Paperless database and API until the 1-hour timeout elapses.

### Evidence
- Redis unacked hash count: `docker exec paperless-redis redis-cli hlen unacked` -> 8.
- Tasks API: 8 tasks remain in status `PENDING` with no worker progress.
- Celery worker log output:
  ```text
  redis.exceptions.ConnectionError: Error while reading from toxiproxy:6379 : (104, 'Connection reset by peer')
  [INFO] [celery.worker.consumer.connection] Connected to redis://toxiproxy:6379//
  ```
  The worker resumes processing newly incoming messages, leaving the 8 unacked tasks orphan in `unacked`.
