# Execution Plan — News Aggregator & Intelligence Reporter

Source of truth: `README.md`. Note: LLM provider selection is one thin `summarize(text) -> str` function dispatching on `LLM_PROVIDER` — do not build a strategy-pattern class hierarchy for OpenAI vs Ollama.

## Prerequisites
- Docker + Docker Compose
- Python 3.11+ (`feedparser`, `newspaper3k`, `scikit-learn`, `playwright`, `jinja2`)
- `OPENAI_API_KEY` and/or a local Ollama install depending on `LLM_PROVIDER`
- `SENDGRID_API_KEY`, `SLACK_WEBHOOK_URL` (README section 10)

## Build Checklist

- [ ] Create the file/dir tree from README section 7.2; `docker-compose.yml` with `postgres` + `redis` only.
  - Verify: `docker compose up -d postgres redis` → healthy.
- [ ] Write init SQL for `sources`, `categories`, `articles` (+ `pg_trgm` extension/index), `digests` (README section 4).
  - Verify: `\dt` and `\d articles` show the tables and `idx_articles_search`.
- [ ] Implement `ingestion/rss_parser.py` + `tests/test_rss_parser.py` against a saved sample feed.
  - Verify: `pytest tests/test_rss_parser.py -v` passes.
- [ ] Implement `ingestion/text_extractor.py` (newspaper3k) against a saved HTML fixture.
  - Verify: extraction returns non-empty body text.
- [ ] Implement cosine-similarity dedup in `intelligence/nlp_processor.py` + `tests/test_dedup.py`.
  - Verify: 3 near-identical articles flagged, 2 unrelated articles not flagged.
- [ ] Implement TF-IDF categorization against `categories.keywords`.
  - Verify: sample AI and Finance articles categorize correctly.
- [ ] Implement `intelligence/llm_summarizer.py::summarize()` (thin dispatch on `LLM_PROVIDER`) + `tests/test_summarizer.py` (mocked, both providers + timeout fallback).
  - Verify: `pytest tests/test_summarizer.py -v` passes all 3 cases.
- [ ] Implement the 4 API endpoints (README section 5).
  - Verify: each curl example works; `EXPLAIN ANALYZE` on a keyword search shows an index scan via `pg_trgm`.
- [ ] Wire delivery automation (Jinja2 template → SendGrid/Slack, via script or n8n).
  - Verify: a test digest renders correctly grouped by category and sends successfully.
- [ ] Full stack up + smoke test: ingest → dedupe → categorize → summarize → deliver.
  - Verify: generated digest has no duplicate stories.

## Definition of Done
- [ ] `docker compose up -d` brings up `api`, `ingestion_worker`, `n8n`, `postgres`, `redis` healthy.
- [ ] Dedup test proves near-identical articles are collapsed; unrelated ones are not.
- [ ] Summarizer works for the configured `LLM_PROVIDER` and degrades gracefully on timeout/rate-limit.
- [ ] `pytest` full suite green.
