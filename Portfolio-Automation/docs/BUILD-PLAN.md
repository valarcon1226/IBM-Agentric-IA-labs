# Portfolio Automation — Master Build Plan

This file sequences the 12 projects in this portfolio for an executing agent (Gemini CLI). Each project folder has its own `README.md` (architecture, schema, API, docker services — the source of truth) and `EXECUTION_PLAN.md` (the atomic, checkbox-driven build checklist derived from it).

## How to execute this plan

1. Work through the projects **in the order below**, one at a time.
2. For each project: open its `EXECUTION_PLAN.md`, execute and check off items top to bottom, and run that project's own "Testing Strategy" (in its `README.md`) before moving to the next project.
3. Do not start `10-docker-compose-lab` until every other project below it in the order is individually working — it consolidates all of them into one production stack.
4. Do not redesign the architecture in any project's `README.md` — the simplification decisions already baked into each plan (see each README's "Implementation Steps") are final for this build.

## Build order and rationale

| # | Project | Why this position |
|---|---------|--------------------|
| 1 | `01-smart-data-intake` | Foundational FastAPI + Postgres + Redis + MinIO + Streamlit pattern reused by most other projects. Build this first to establish the pattern. |
| 2 | `04-data-cleaning-api` | Reuses the cleaning-logic patterns from project 1 (kept as a separate service, not merged). |
| 3 | `03-multi-channel-notifier` | Needed as a dependency by project 4 in this order (`06-scheduler-engine`) for alerting on consecutive failures. |
| 4 | `06-scheduler-engine` | Integrates with `03`'s notification hub for failure alerts. |
| 5 | `05-invoice-processor` | Independent; adds OCR/document-processing skill to the portfolio. |
| 6 | `02-business-registry-enricher` | Independent; adds external API integration + rate-limiting patterns. |
| 7 | `08-lead-generator` | Independent; adds scraping + fuzzy-dedup patterns reused by project 8. |
| 8 | `07-price-monitor` | Builds on `08`'s scraping/anti-bot patterns; reuses `03`'s alerting for price-drop notifications. |
| 9 | `09-news-aggregator` | Reuses the n8n orchestration pattern from `01` and the templating/delivery approach from `03`. |
| 10 | `11-monitoring-dashboard` | Instruments the services built in steps 1-9 — needs real services to monitor before it's useful. |
| 11 | `12-ci-cd-pipeline` | Can also be applied incrementally per-project starting right after `01` instead of waiting until here — both are valid; this position assumes a single pipeline pass once there's enough real code across services to make the security/coverage gates meaningful. |
| 12 | `10-docker-compose-lab` | **Last.** Consolidates all 11 other projects into one production topology (shared Postgres, shared Redis, Traefik routing) — see that project's `README.md` Step 0. |

## Cross-project decisions already applied (don't re-litigate)

- No project uses Alembic/migrations tooling for this first build — every schema is applied via a plain init SQL file mounted into the DB container.
- `03-multi-channel-notifier` uses **Redis** as its Celery broker (not RabbitMQ), since Redis is already required infra in `01`, `04`, `06`, `07`, `08`.
- `02-business-registry-enricher` has **no Redis service at all** — rate limiting is in-process via `aiolimiter`.
- `04-data-cleaning-api` ships with **Pandas only**; Polars is deferred until a specific endpoint is profiled and shown too slow.
- `06-scheduler-engine` uses the `sqlalchemy-celery-beat` package (`DatabaseScheduler`) instead of a hand-rolled Celery Beat scheduler class. *(Changed 2026-09-24 from `celery-sqlalchemy-scheduler`, which has had no release since 2021-04.)*
- `07-price-monitor` stores screenshots on a **local disk volume** (no S3/MinIO) until/unless merged into `10`'s shared stack.
- `08-lead-generator` uses `rapidfuzz` (not the unmaintained `fuzzywuzzy`/`python-Levenshtein`).
- `09-news-aggregator`'s LLM provider selection is one thin `summarize()` function dispatching on `LLM_PROVIDER`, not a class hierarchy.
- `11-monitoring-dashboard` only instruments/scrapes services that already exist — add coverage incrementally as more projects come online.
- `10-docker-compose-lab` is the only project that shares infrastructure (one Postgres, one Redis) across services; every other project keeps its own standalone `docker-compose.yml` for independent dev/demo.
