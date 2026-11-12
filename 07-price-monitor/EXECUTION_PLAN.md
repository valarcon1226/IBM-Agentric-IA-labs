# Execution Plan — E-Commerce Price Monitor (Polite Scraping)

Source of truth: `README.md` and `docs/tasks/07-B-price-monitor.md`.

## Prerequisites
- Docker + Docker Compose
- Python 3.12+ / uv
- Respect polite scraping: robots.txt, 1 req/s per domain, identifiable User-Agent (`PriceMonitorBot/1.0`), no proxies or evasion.

## Build Checklist

- [ ] Repository skeleton, dependencies, and configuration:
  - `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.env.example`, `.gitignore`.
- [ ] Database layer:
  - `init-db.sql` and SQLAlchemy models (`Product`, `PriceHistory`, `Alert`, `ScrapingLog`).
- [ ] Demo store:
  - Nginx static site (`demo-store/html/`) with `keyboard.html` and `headphones.html` (JSON-LD Product + CSS selectors).
  - Price modification script: `demo-store/update_price.py`.
- [ ] Polite scraper module:
  - `PoliteFetcher` with robots.txt check, 1 req/s rate limit, and tenacity exponential backoff on 429/5xx.
  - Parsers for MercadoLibre public API (`https://api.mercadolibre.com/items/{id}`) and HTML (JSON-LD Product/Offer + CSS selector fallback).
  - Playwright fallback with Edge (`channel="msedge"`) when `requires_js` is True.
  - Alert manager: triggers webhook to `WEBHOOK_ALERT_URL` upon price drop or threshold breach.
- [ ] Celery tasks & scheduler:
  - Celery app with Redis broker.
  - `scrape_product` worker task and `check_all_active_products` beat schedule.
- [ ] FastAPI backend:
  - CRUD for products, history retrieval, CSV export, force scrape, and Bearer token security.
  - Unauthenticated `/health` endpoint.
- [ ] Streamlit dashboard:
  - Plotly price curve visualizations, metrics, and alert logs.
- [ ] Docker compose infrastructure:
  - Services: `postgres`, `redis`, `api` (port 8007), `dashboard` (port 8507), `demo-store` (port 8087), `worker`, `beat`, `webhook-sink`.
  - Postgres and Redis not published to host.
- [ ] Test suite:
  - Unit tests with mock fixtures (HTML files and MercadoLibre API mock).
  - Integration tests against running Docker compose stack.
  - E2E verification script (`scripts/verify_e2e.py`).

## Definition of Done
- `ruff check .` passes without errors.
- `pytest -q` passes all unit tests.
- `docker compose up -d --build` starts all services healthy.
- `docker compose ps` shows all services up.
- `pytest -m integration -q` passes against the compose stack.
- `python scripts/verify_e2e.py` runs the end-to-end flow: registers 2 products from demo store, drops headphones price with `update_price.py`, verifies history, and confirms webhook alert delivery.
- `docker compose down -v` cleanly shuts down and removes volumes.
