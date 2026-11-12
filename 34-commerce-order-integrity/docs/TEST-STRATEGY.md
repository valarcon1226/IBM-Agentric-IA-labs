# Test Strategy — Project 34: E-Commerce Order Integrity (Saleor)

## 1. System Under Test (SUT) Architecture

- **Core Backend:** Saleor 3.20 (`ghcr.io/saleor/saleor:3.20`), Django 4.2 + GraphQL ASGI service.
- **Async Processing:** Celery worker with Redis broker (`redis:7.4-alpine`).
- **Persistence:** PostgreSQL 15 (`postgres:15-alpine`).
- **Staff Interface:** Saleor Dashboard 3.20 (`ghcr.io/saleor/saleor-dashboard:3.20`).
- **Network Fault Injection:** Toxiproxy 2.11 (`ghcr.io/shopify/toxiproxy:2.11.0`).

---

## 2. The Testing Pyramid and UI Scope Justification

A cornerstone of the 2026 test automation strategy is maintaining an efficient, deterministic, and fast-feedback test pyramid.

```text
               /  \
              / UI \             Top Layer: 5 Critical Staff Journeys
             / Tests\            (Cross-browser: Edge, Firefox, WebKit)
            /--------\
           /Resilience\          Middle Layer: Concurrency Races, Webhook
          /& Migrations\         Backpressure, Toxiproxy Network Drops
         /--------------\
        /   GraphQL API  \       Foundation Layer: Schema Contracts, Pydantic v2,
       /  & Unit Tests    \      Cursor Pagination (Hypothesis), Bulk Isolation
      /--------------------\
```

### Why Exactly 5 UI Tests?

In high-throughput e-commerce systems, end-to-end UI automation carries substantial overhead:
1. **Flakiness and Browser Overhead:** UI suites that replicate business logic validations (such as verifying pagination or calculating tax breakdowns) suffer from non-deterministic rendering delays, DOM hydration latency, and elevated resource contention.
2. **Shift-Left Discipline:** Data integrity, inventory concurrency, idempotency guarantees, and bulk error reporting belong strictly at the API and database levels where thousands of transactions can be validated deterministically in seconds.
3. **The 5 Staff Golden Paths:**
   - **Login (`test_01_staff_login`):** Validates staff session authentication, JWT exchange, and administrative route guards.
   - **Order Discovery (`test_02_find_order`):** Verifies the staff member can locate orders and render details through the data grid.
   - **Fulfillment (`test_03_fulfill_order`):** Verifies the staff fulfillment modal, inventory allocation transitions, and warehouse shipping updates.
   - **Partial Refund (`test_04_issue_partial_refund`):** Verifies the staff financial adjustment interface and communication with the payment gateway.
   - **Timeline Audit (`test_05_see_refund_in_order_history`):** Verifies that financial and status modifications are immutably appended to the order audit history.

All state preparation (order creation, checkout completion, mock payment charging) is performed via direct API mutations and database seeds. The UI test strictly tests the user interaction path.

---

## 3. Test Layers and Tooling

| Layer | Focus | Tools / Frameworks | Execution Frequency |
|---|---|---|---|
| **API Contracts** | Response shape conformance, Relay cursor pagination, bulk error isolation | `pytest`, `httpx`, `pydantic v2`, `hypothesis` | PR Gate (`p1`) |
| **Resilience & Faults** | Connection drop retries, idempotency key verification, webhook retry backoff | `toxiproxy`, stdlib `http.server` (`ThreadingHTTPServer`) | Nightly / Resilience |
| **Concurrency & Race** | Zero overselling isolation under concurrent checkout competition | `asyncio`, `psycopg3`, PostgreSQL | Nightly / Resilience |
| **Schema Migration** | N-1 to N data and financial checksum preservation, snapshot rollback | PostgreSQL `pg_dump`, `psql`, MD5 checksums | Nightly / Migration |
| **Staff UI** | Core administrative operations and visual workflow verification | `pytest-playwright` (Edge, Firefox, WebKit) | PR Gate / Nightly |
| **Load & Performance** | Listing and checkout throughput, latency SLAs (p50, p95, p99) | `locust` (headless, 10 concurrent users) | Nightly / Perf |

---

## 4. Traceability and Quality Gates

- Every automated test is annotated with its requirement identifier via `@pytest.mark.req("REQ-...")`.
- The `qa_common.plugin` generates an updated `docs/TRACEABILITY.md` matrix after test execution.
- Quality gates fail automatically if measured percentiles exceed limits defined in `targets.toml`.
