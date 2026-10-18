# Project 34: E-Commerce Order Integrity Suite (Saleor)

Automated quality and resilience engineering suite evaluating transaction consistency, concurrency isolation, asynchronous webhook delivery, and zero-downtime schema migrations on **Saleor 3.20**.

---

## 1. System Under Test (SUT)

The system under test uses pinned container images binding strictly to `127.0.0.1`:

| Service | Pinned Image / Version | Port |
|---|---|---|
| **Saleor Core API** | `ghcr.io/saleor/saleor:3.20` | `127.0.0.1:8002` |
| **Saleor Celery Worker** | `ghcr.io/saleor/saleor:3.20` | Internal |
| **Saleor Dashboard** | `ghcr.io/saleor/saleor-dashboard:3.20` | `127.0.0.1:9000` |
| **PostgreSQL** | `postgres:15-alpine` | `127.0.0.1:5433` |
| **Redis** | `redis:7.4-alpine` | `127.0.0.1:6379` |
| **Toxiproxy** | `ghcr.io/shopify/toxiproxy:2.11.0` | `127.0.0.1:8000`, `127.0.0.1:8474` |

---

## 2. Production Concerns Coverage

Every production concern is evaluated against real open-source software:

| Concern | How It Is Tested |
|---|---|
| **Pagination** | Hypothesis property-based walk across product catalog (pages 1 to 100) asserting zero duplicates and exact set equivalence against direct SQL queries. Concurrent insertions during walk verify zero skipped pre-existing items. Exceeding max limit (100) returns documented error (`saleor/graphql/core/connection.py:387`). Large-scale cursor pagination walk traverses 2,000 seeded orders with zero duplicates. |
| **Retries & Idempotency** | Toxiproxy downstream connection drop injected right after `checkoutComplete` reaches the server. Client retries with identical idempotency parameters across 50 runs, verifying strictly 1 order created. |
| **Backpressure & Concurrency** | 50 concurrent async tasks compete for the last 5 inventory units. Webhook queue tested under slow consumer conditions (2.0s delay) asserting queue buffering and delivery lag SLAs. |
| **Partial Failures** | Webhook consumer injects 30% HTTP 500 errors; Celery backoff retry policy verified for 100% recovery. `productBulkCreate` called with 100 rows (10 invalid in 3 modes: blank field, invalid category, duplicate slug) asserting 90 valid rows created, exact row error mapping, and zero partial records in SQL. |
| **Schema Migrations** | Upgrade from N-1 (`3.19`) to N (`3.20`) with 50 seeded orders and payments. MD5 checksums of orders, order lines, totals, stock and payments compared before and after (41 migrations in 12.54 s, 0 diffs). Rollback: drop and recreate the database, restore the pre-upgrade `pg_dump`, boot 3.19 on it and compare the checksums again. Restoring the dump over the 3.20 schema fails, because 3.20 adds a foreign key the 3.19 dump cannot drop. |

---

## 3. Numerical Targets & Measured SLA Performance

> **Where the numbers come from:** GitHub Actions on `ubuntu-latest` (4 vCPU, 16 GB), the hardware the targets assume. PR gate: [run 39147961900](https://github.com/valarcon1226/IBM-Agentric-IA-labs/actions/runs/39147961900). Nightly (resilience, migration, perf): [run 39147962708](https://github.com/valarcon1226/IBM-Agentric-IA-labs/actions/runs/39147962708), whose `nightly-metrics` artifact holds `results/metrics.json`. Rows marked *local* were measured on the laptop on 2026-10-17 because the CI log does not print them.

| Target | Target value (`targets.toml`) | Measured | Result |
|---|---|---|---|
| **Checkout create → complete, p95 at 10 users for 5 min** | ≤ 1,500 ms | **200 ms** (p50 140 ms, 702 checkouts, 0 errors) | PASS |
| **`products(first: 100)` query, p95** | ≤ 400 ms | **50 ms** (p50 32 ms, 2,107 queries, 0 errors) | PASS |
| **Oversells across 20 race runs** | 0 | Defect reproduced in CI (`xfail` held). *Local:* 18 oversells in 10/20 runs, then 11 in 8/20 (stock down to -3) | DEFECT (`FINDING-001`) |
| **Duplicate orders across 50 retry runs** | 0 | **0** | PASS |
| **Webhook delivery p95, healthy receiver** | ≤ 5 s | Not measured | — |
| Webhook lag, slow receiver (2 s per call), 500 orders | no target | p50 139 s, p95 262 s, 500/500 delivered: the queue grows but loses nothing | — |
| **Events delivered within 10 min under 30% HTTP 500** | 100% | **100%** (500/500; 199 failed attempts retried, average retry gap 10.03 s, matching Saleor's 10 s backoff) | PASS |
| **Checksum differences after 3.19 → 3.20 upgrade** | 0 | **0** across 6 checksums (41 migrations in 13.14 s) | PASS |
| Order pagination walk | every ID once | 2,000 orders, 0 duplicates | PASS |
| **PR gate / nightly wall clock** | ≤ 12 min / ≤ 60 min | **5.0 min / 34.3 min** | PASS |

---

## 4. Findings and Defects in SUT

Detailed evidence, source code citations, reproduction steps, and SQL queries are preserved in [`docs/FINDINGS.md`](docs/FINDINGS.md).

### FINDING-001: Race Condition in Stock Allocation Leads to Inventory Overselling
- **Component:** `saleor.warehouse.management.allocate_stocks` / `saleor.checkout.complete_checkout`
- **Severity:** High
- **Status:** Documented / Marked `@pytest.mark.xfail(strict=True, reason="FINDING-001")`
- **Root Cause:** In `ghcr.io/saleor/saleor:3.20`, file `saleor/warehouse/management.py` (lines 121–136), `stocks_id = (stock.pop("id") for stock in stocks)` is created as a single-use generator expression. The reservation availability check evaluates and exhausts the generator in `_prepare_stock_to_reserved_quantity_map`. The subsequent database query `Allocation.objects.filter(stock_id__in=stocks_id)` receives an empty sequence, rendering the allocation check ineffective under high concurrency.
- **Evidence:** 20 race runs of 50 concurrent buyers competing for 5 units caused 18 oversold units in 10 of 20 runs, driving inventory balances negative (down to -3).

### FINDING-002: Intra-Batch Duplicate Slug in `productBulkCreate` Triggers Unhandled IntegrityError
- **Component:** `saleor.graphql.product.bulk_mutations.product_bulk_create.ProductBulkCreate`
- **Severity:** Medium
- **Status:** Documented
- **Root Cause:** In `ProductBulkCreate.clean_base_fields`, if `slug` is provided by the client, it is not checked against duplicate slugs within the same batch. When `Product.objects.bulk_create` executes, PostgreSQL raises `UniqueViolation`, which crashes the GraphQL request with an unhandled 500 error instead of isolating row errors with `errorPolicy: REJECT_FAILED_ROWS`.

---

## 5. Staff Dashboard Golden Paths (5 UI Tests)

Executed with `--repeat-each 3` (15 test executions per engine) across **Microsoft Edge**, **Firefox**, and **WebKit** using `pytest-playwright`:
1. `test_01_staff_login`: Staff credential authentication and administrative routing.
2. `test_02_find_order`: Discovery and header rendering of order details.
3. `test_03_fulfill_order`: Full warehouse fulfillment dispatch and state transition.
4. `test_04_issue_partial_refund`: Financial adjustment and payment gateway refund registration.
5. `test_05_see_refund_in_order_history`: Audit timeline validation confirming immutable event logging.

*Results:*
- **Microsoft Edge (`msedge`):** 15/15 passed in 60.52 s
- **Firefox (`firefox`):** 15/15 passed in 74.63 s
- **WebKit (`webkit`):** 15/15 passed in 71.73 s

---

## 6. Known Limits

- **Webhook burst on the laptop:** with the worker capped at `mem_limit: 512m` it reached 511.5 MiB at 500 orders, so local runs use `WEBHOOK_BURST_COUNT=50`. CI runs the full 500.
- **Local numbers:** the oversell counts come from the laptop; CI only records that the `xfail` held.
- **Locust:** the load test turns off inventory tracking for its one variant, so 704 checkouts do not run out of stock. It measures checkout latency, not stock contention. The stock race test covers contention.
- **Migration test is destructive:** it runs `docker compose down -v` and rebuilds the stack, so it runs in its own nightly step.

## 7. How to Run

### Setup and Linting
```powershell
uv venv -p 3.12 .venv
.venv\Scripts\activate
uv sync
uv run ruff check .
uv run mypy tests scripts
```

### Run Tests by Layer
```powershell
# Fast PR gate (API contracts, pagination, bulk import, unit tests)
uv run pytest -m "p1 and not (resilience or migration or perf)" -v

# Cross-browser UI tests (with 3 repeats each)
uv run pytest tests/ui/test_dashboard_orders.py --browser chromium --browser-channel msedge --repeat-each 3 -v
uv run pytest tests/ui/test_dashboard_orders.py --browser firefox --repeat-each 3 -v
uv run pytest tests/ui/test_dashboard_orders.py --browser webkit --repeat-each 3 -v

# Resilience and fault injection
uv run pytest -m "resilience" -v

# Schema migration & checksum preservation
uv run pytest -m "migration" -v -s

# Headless Locust performance benchmark (5 minutes)
uv run locust -f tests/perf/locustfile.py --headless -u 10 -r 2 --run-time 5m --host http://127.0.0.1:8000
```
