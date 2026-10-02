# Execution Plan — EU Business Registry Enricher

Source of truth: `README.md`. Note: this plan drops Redis entirely (rate limiting is in-process via `aiolimiter`) — do not add a `redis` service back in.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`fastapi`, `zeep`, `aiolimiter`, `tenacity`, `sqlalchemy`)
- `CH_API_KEY` and `INSEE_API_KEY` (README section 11) — sandbox/test keys are fine for local dev
- `psql` via `docker compose exec` for verification

## Build Checklist

- [x] Create the file/dir tree from README section 8; `docker-compose.yml` with only `postgres`.
  - Verify: `docker compose up -d postgres` → healthy.
- [x] Write `init-db.sql` for `company_cache` and `api_logs` (README section 4).
  - Verify: `\dt` lists both tables.
- [x] Implement unified Pydantic request/response models in `app/models.py`.
  - Verify: `python -c "import app.models"` succeeds.
- [x] Implement `app/registries/vies.py` (Zeep SOAP client) + `tests/test_vies.py` against VIES's own test VAT numbers.
  - Verify: `pytest tests/test_vies.py -v` passes.
- [x] Implement `app/registries/companies_house.py` with `aiolimiter.AsyncLimiter(600, 300)` + `tenacity` + mocked unit test.
  - Verify: test asserts the 601st call in a 5-minute window is throttled.
- [x] Implement `app/registries/insee.py` with `aiolimiter.AsyncLimiter(30, 60)` + `tenacity` + mocked unit test.
  - Verify: `pytest` passes.
- [x] Implement cache-read logic: `WHERE last_updated > NOW() - INTERVAL '30 days'`, no separate expiry job.
  - Verify: unit test with a stale row (31 days old) triggers a registry call; a fresh row does not. `tests/test_cache.py` + `tests/test_enrichment.py`.
- [x] Implement `POST /api/v1/enrich` with country routing + cache-first lookup.
  - Verify: curl example from README section 5 — first call `"cached": false`, repeat call `"cached": true`. Covered by `tests/test_enrich_api.py` (mocked connectors) and `tests/test_integration_e2e.py` (real stack, cached rows only — see Dudas below).
- [x] Implement `GET /api/v1/enrich/{country}/{identifier}` with `force_refresh`.
  - Verify: `tests/test_enrich_api.py` (404/502/force_refresh) and `tests/test_integration_e2e.py`.
- [x] Add `n8n` service to `docker-compose.yml` and export `n8n/workflows/enrich.json` (Webhook → HTTP Request → Set → Google Sheets), placeholders only.
  - Verify: `python -m json.tool n8n/workflows/enrich.json` succeeds; `docker compose --env-file .env.example up -d --build --wait` reports `n8n` healthy.

## Definition of Done
- [x] `docker compose up -d` brings up `postgres`, `enricher_api`, `n8n` (no `redis` service). Verified with `docker compose --env-file .env.example up -d --build --wait` → all 3 healthy.
- [ ] `curl -X POST .../api/v1/enrich` (README section 5 payload) returns correct company data for both a GB and FR identifier **from the real registries**. This needs real `CH_API_KEY`/`INSEE_API_KEY` values, which are not available in this environment — left unchecked. The cache-served path (`cached: true`) for both countries is verified end-to-end by `tests/test_integration_e2e.py`, and the `cached: false` registry-call path is covered with mocked connectors by `tests/test_enrich_api.py`.
- [x] Rate limiter test proves throttling works without Redis. `tests/test_rate_limiter.py`.
- [x] Cache TTL test proves 30-day staleness logic works via the plain SQL `WHERE` clause. `tests/test_cache.py`.
- [x] `pytest` full suite green, no live registry calls made during CI (VIES test numbers + mocked CH/INSEE). `python -m pytest -q` → 61 passed, 6 deselected (integration/e2e/live).
