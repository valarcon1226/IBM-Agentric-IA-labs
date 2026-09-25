# Execution Plan — E-Commerce Price Monitor

Source of truth: `README.md`. Note: screenshots go to a **local disk volume** for this standalone build, not S3/MinIO.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`playwright`, `playwright-stealth`, `celery`, `fastapi`, `streamlit`, `plotly`)
- `playwright install chromium` run once locally
- Build after `08-lead-generator` (reuses its scraping/anti-bot patterns) and after `03-multi-channel-notifier` (reuses its alerting approach) per the portfolio's recommended build order

## Build Checklist

- [ ] Create the file/dir tree from README section 7.2; `docker-compose.yml` with `postgres` + `redis` only.
  - Verify: `docker compose up -d postgres redis` → healthy.
- [ ] Write init SQL for `products`, `price_history`, `alerts`, `scraping_logs` (README section 4).
  - Verify: `\dt` lists all 4.
- [ ] Create a local `./screenshots/` volume mounted into `celery_worker`.
  - Verify: a test file written by the worker is visible on the host volume.
- [ ] Implement `scraper/parsers/amazon.py` + `mercadolibre.py` + `tests/test_parsers.py` against saved HTML fixtures.
  - Verify: `pytest tests/test_parsers.py -v` passes.
- [ ] Wire Playwright + `playwright-stealth` + proxy/UA rotation into `scraper/tasks.py`.
  - Verify: run against https://bot.sannysoft.com/ — no failed stealth checks.
- [ ] Configure Celery Beat to enqueue scrapes per active product on its interval.
  - Verify: a 1-minute test-interval product gets a new `price_history` row within ~90s.
- [ ] Implement alerting (Telegram + email) on threshold crossing + `tests/test_alerts.py` (mocked).
  - Verify: simulated price drop triggers exactly one Telegram call and one email call.
- [ ] Implement the 5 API endpoints (README section 5).
  - Verify: each curl example returns the documented shape.
- [ ] Build the Streamlit + Plotly dashboard.
  - Verify: newly added product appears and its price history renders as a line chart.
- [ ] Full stack up + smoke test with the Sony WH-1000XM5 example product.
  - Verify: forced scrape produces a `price_history` row (and an `alerts` row if under target price).

## Definition of Done
- [ ] `docker compose up -d` brings up all 6 services healthy.
- [ ] `curl -X POST .../api/v1/products/` (README section 5 example) registers a product successfully.
- [ ] Anti-bot test against bot.sannysoft.com shows no failed fingerprint checks.
- [ ] Alert test proves both Telegram and email fire on a simulated threshold breach.
- [ ] `pytest` full suite green.
