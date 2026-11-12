# Execution Plan — News Aggregator & Intelligence Reporter

Source of truth: `README.md`. Note: LLM provider selection is one thin `summarize(text) -> str` function dispatching on `LLM_PROVIDER` with robust fallback to text extraction.

## Prerequisites
- Docker + Docker Compose
- Python 3.12 (`feedparser`, `trafilatura`, `scikit-learn`, `psycopg`, `pgvector`, `jinja2`, `celery`, `redis`, `fastapi`)
- Local or containerized fake LLM / Ollama (`nomic-embed-text` and `llama3:8b`)
- Mailpit for local SMTP delivery and testing

## Build Checklist

- [x] Create the file/dir tree from README section 7.2; `docker-compose.yml` with `postgres` (pgvector), `redis`, `mailpit`, `fake_llm`, `api`, `worker`.
  - Verify: `docker compose up -d` → healthy.
- [x] Write init SQL for `sources`, `categories`, `articles` (+ `pg_trgm`, `vector` extensions/indexes), `digests`, `digest_articles` (`db/schema.sql`).
  - Verify: tables and indexes created successfully.
- [x] Implement `ingestion/rss_parser.py` + `tests/test_rss_parser.py` against saved sample feeds.
  - Verify: `pytest tests/test_rss_parser.py -v` passes.
- [x] Implement `ingestion/text_extractor.py` (trafilatura + robots.txt compliance) against saved HTML fixture.
  - Verify: extraction returns clean body text; robots.txt respected.
- [x] Implement two-step deduplication (SHA-256 hash + pgvector cosine similarity, with scikit-learn TF-IDF fallback) in `intelligence/nlp_processor.py` + `tests/test_dedup.py`.
  - Verify: cross-source duplicate articles flagged and linked to parent; unrelated articles preserved.
- [x] Implement keyword categorization against `categories.keywords` (`tests/test_categorization.py`).
  - Verify: sample AI, Cybersecurity, Cloud, Fintech articles categorize correctly.
- [x] Implement `intelligence/llm_summarizer.py::summarize()` + `tests/test_summarizer.py` (mocked, timeout fallback).
  - Verify: `pytest tests/test_summarizer.py -v` passes.
- [x] Implement API endpoints (`api/routes.py` with Bearer token security, CRUD sources, articles search with pg_trgm, digests).
  - Verify: `tests/test_api.py` passes all CRUD and search scenarios.
- [x] Wire delivery automation (Jinja2 template → SMTP to Mailpit in `delivery/notifier.py`).
  - Verify: digest renders grouped by category and dispatches to Mailpit.
- [x] Full stack up + smoke test: ingest → dedupe → categorize → summarize → deliver (`scripts/run_demo.py` and `tests/test_integration.py`).
  - Verify: generated digest has no duplicate stories and includes cross-source references.

## Definition of Done
- [x] `docker compose up -d --build` brings up `postgres`, `redis`, `mailpit`, `fake_llm`, `api`, `worker` healthy.
- [x] Dedup test proves cross-source duplicate articles are collapsed to 1 parent + linked duplicates.
- [x] Summarizer works for configured provider and degrades gracefully on timeout/rate-limit.
- [x] `pytest` full suite green.
