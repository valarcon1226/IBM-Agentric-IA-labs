# Execution Plan — EU Business Registry Enricher

Source of truth: `README.md`. Note: this plan drops Redis entirely (rate limiting is in-process via `aiolimiter`) — do not add a `redis` service back in.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`fastapi`, `zeep`, `aiolimiter`, `tenacity`, `sqlalchemy`)
- `CH_API_KEY` and `INSEE_BEARER_TOKEN` (README section 11) — sandbox/test keys are fine for local dev
- `psql` via `docker compose exec` for verification

## Build Checklist

- [ ] Create the file/dir tree from README section 8; `docker-compose.yml` with only `postgres`.
  - Verify: `docker compose up -d postgres` → healthy.
- [ ] Write `init-db.sql` for `company_cache` and `api_logs` (README section 4).
  - Verify: `\dt` lists both tables.
- [ ] Implement unified Pydantic request/response models in `app/models.py`.
  - Verify: `python -c "import app.models"` succeeds.
- [ ] Implement `app/registries/vies.py` (Zeep SOAP client) + `tests/test_vies.py` against VIES's own test VAT numbers.
  - Verify: `pytest tests/test_vies.py -v` passes.
- [ ] Implement `app/registries/companies_house.py` with `aiolimiter.AsyncLimiter(600, 300)` + `tenacity` + mocked unit test.
  - Verify: test asserts the 601st call in a 5-minute window is throttled.
- [ ] Implement `app/registries/insee.py` with `aiolimiter.AsyncLimiter(30, 60)` + `tenacity` + mocked unit test.
  - Verify: `pytest` passes.
- [ ] Implement cache-read logic: `WHERE last_updated > NOW() - INTERVAL '30 days'`, no separate expiry job.
  - Verify: unit test with a stale row (31 days old) triggers a registry call; a fresh row does not.
- [ ] Implement `POST /api/v1/enrich` with country routing + cache-first lookup.
  - Verify: curl example from README section 5 — first call `"cached": false`, repeat call `"cached": true`.

## Definition of Done
- [ ] `docker compose up -d` brings up `postgres`, `enricher_api`, `n8n` (no `redis` service).
- [ ] `curl -X POST .../api/v1/enrich` (README section 5 payload) returns correct company data for both a GB and FR identifier.
- [ ] Rate limiter test proves throttling works without Redis.
- [ ] Cache TTL test proves 30-day staleness logic works via the plain SQL `WHERE` clause.
- [ ] `pytest` full suite green, no live registry calls made during CI (VIES test numbers + mocked CH/INSEE).
