# Execution Plan — B2B Lead Generator

Source of truth: `README.md`. Note: use **`rapidfuzz`** (not `fuzzywuzzy`/`python-Levenshtein`) everywhere — same API, maintained, faster.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`playwright`, `httpx`, `beautifulsoup4`, `pandas`, `rapidfuzz`, `phonenumbers`, `tenacity`, `celery`)
- `playwright install chromium` run once locally

## Build Checklist

- [x] Create the file/dir tree from README section 7.2; `docker-compose.yml` con `api`, `postgres` y `demo-directory`.
  - Verify: `docker compose up -d` → healthy.
- [x] Write init SQL for `scraping_sessions`, `leads` (with GIN index), `dedup_log` (README section 4).
  - Verify: `\dt` and `\d leads` show the tables and the `idx_leads_search` index.
- [x] Implement `normalize_phone()` + `tests/test_enrichment.py`.
  - Verify: `pytest tests/test_enrichment.py -v` passes (extensions, missing country code cases).
- [x] Implement `deduplicate_leads()` using `rapidfuzz.fuzz.token_sort_ratio` + `tests/test_dedup.py`.
  - Verify: `pytest tests/test_dedup.py -v` — overlapping records merge correctly.
- [x] Implement `core/scrapers/yellow_pages.py` (httpx + BeautifulSoup) con `tenacity` backoff on 429/5xx.
  - Verify: mocked 429 triggers exponential backoff (visible in logs/test assertion).
- [x] Implement `core/scrapers/google_maps.py` (Playwright, scroll pagination).
  - Verify: mocked/saved results page yields multiple pages of results.
- [x] Wire MX-record email validation into `core/enrichment.py`.
  - Verify: valid-domain email passes, invalid-domain email fails.
- [x] Implement `POST /api/v1/jobs/` (scrape → enrich → dedup → score → persist chain).
  - Verify: curl example from README section 5 returns a job id; `GET /api/v1/jobs/{id}` reaches `COMPLETED`.
- [x] Implement `GET /api/v1/leads/`, `/leads/export`, `POST /api/v1/config/dedup`.
  - Verify: `/leads/export` returns a valid CSV.
- [x] Full stack up + smoke test with `"accounting firm", "Austin, TX"`.
  - Verify: deduplicated, scored leads appear in Postgres.

## Definition of Done
- [x] `docker compose up -d` brings up `postgres`, `api` and `demo-directory` healthy.
- [x] A real job run produces deduplicated leads with scores per README section 3.2.
- [x] `pytest` full suite green, including the rate-limit backoff test.
- [x] No `fuzzywuzzy`/`python-Levenshtein` dependency present anywhere in the codebase.
