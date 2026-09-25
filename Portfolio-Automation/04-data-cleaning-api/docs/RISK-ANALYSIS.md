# Risk Analysis — Data Cleaning & Transformation API

**Analysis date:** 2026-09-24
**Basis:** source review of `app/`, execution of the test suite, and `ruff`/`mypy` results. No
production traffic or load data exists yet, so probability ratings are qualitative estimates.

Priority reflects consequence for a client relying on this service and test urgency — not proof
that a defect exists unless the Status column says it was observed.

| Risk ID | Risk                                                                                    | Prob.  | Impact | Priority | Status                  | Response                                                                                                               |
| ------- | --------------------------------------------------------------------------------------- | ------ | ------ | -------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| DC-R01  | The deployed app does not expose the documented `/api/v1/*` endpoints.                  | High   | High   | Critical | **Observed → fixed**    | Routers were never registered in `app/main.py`; tests masked it by building their own app. Tests now import the real app. |
| DC-R02  | Cleaning silently drops, duplicates, or mistypes data.                                  | Medium | High   | Critical | Partially covered       | Unit-test each cleaning option on small DataFrames; compare row counts and dtypes explicitly.                           |
| DC-R03 | Endpoints are reachable without authentication. | High | High | Critical | **Observed → fixed** | All `/api/v1` routers now depend on `verify_api_key`; missing or wrong key → 401 (tested). `/health` stays public. |
| DC-R04  | Async jobs never report progress or results.                                            | High   | High   | Critical | **Observed, open**      | `update_job_status` is a no-op and `/jobs` reads an in-memory mock. Persist job state in Postgres; test transitions.    |
| DC-R05 | Malformed input (bad CSV, wrong encoding) returns 500 instead of an actionable 4xx. | High | Medium | High | **Observed → fixed** | Bad options JSON, empty and non-UTF-8 files return 400 (tested). Excel/JSON parsing arrives with DC-R09. |
| DC-R06  | Large files are processed inline, blocking the API or exhausting memory.                | Medium | High   | High     | Covered                 | Size threshold routing is tested with a stubbed queue.                                                                 |
| DC-R07  | User-created schemas cannot be used for validation and vanish on restart.              | High   | Medium | High     | **Observed, open**      | `/schemas` writes to a module-level list; `/validate` only reads `MOCK_SCHEMAS`. Persist and unify both.               |
| DC-R08 | Configuration drift: the service boots but reads different variables than documented. | Medium | Medium | High | **Observed → fixed** | `.env.example` completed; storage now reads `settings` (single `MINIO_BUCKET`), unused Celery vars removed. Contract + bucket tests added. |
| DC-R09  | README advertises Excel/JSON input that the code does not accept.                       | High   | Medium | High     | **Observed, open**      | Only `pd.read_csv` is used. Either implement or narrow the claim.                                                       |
| DC-R10  | Health check reports healthy while a dependency is down (or vice versa).                | Low    | Medium | Medium   | **Observed → fixed**    | `db.execute("SELECT 1")` fails under SQLAlchemy 2.0; now uses `text()` and 200/503 paths are tested.                  |
| DC-R11  | Transform/enrich helpers produce wrong shapes or values.                                | Medium | Medium | Medium   | Not covered             | Add unit tests for `transformer.py` and `enricher.py` before relying on them.                                          |
| DC-R12 | 500 responses leak internal exception text. | Medium | Low | Low | **Observed → fixed** | 500s return a generic message; the exception is logged server-side (tested). |
| DC-R13  | README examples drift from the real request/response contract.                         | High   | Medium | High     | **Observed → fixed**    | README transform/enrich examples returned 422; rewritten from code and asserted verbatim by tests. |

## Priority response

- **Critical:** block any "production-ready" claim until covered or fixed.
- **High:** cover in the next iteration; document current behaviour honestly in the README.
- **Medium / Low:** cover when the related code changes or evidence raises the risk.

Ratings must be revised from execution evidence, not assumptions. See
[`TRACEABILITY-MATRIX.md`](TRACEABILITY-MATRIX.md) for which scenarios and tests address each risk.
