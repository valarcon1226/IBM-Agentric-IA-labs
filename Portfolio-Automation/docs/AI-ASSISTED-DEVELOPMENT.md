# AI-Assisted Development

AI coding agents (Gemini CLI, Claude Code, Codex) are used in this portfolio to draft designs,
build plans, code and tests. They speed up the work; they do not decide what is true about it.

## How AI output is used

- Architecture and build plans (`README.md`, `EXECUTION_PLAN.md`) are drafted with AI, then
  reviewed and simplified by hand — e.g. dropping RabbitMQ for Redis, Polars for Pandas only,
  and Alembic for plain init SQL (see [`BUILD-PLAN.md`](BUILD-PLAN.md)).
- Generated code is accepted only after it passes lint, type-check and tests in CI.

## Required controls

- **Run it, don't trust it.** A generated test that passes is checked against the real
  production object. In project 04 the original AI-written API tests built their own FastAPI
  app, so they passed even though the deployed app exposed no `/api/v1` routes.
- **Status claims come from evidence.** A feature is marked working only when a test proves it;
  everything else stays `Designed`, `Stubbed` or `Not Implemented`.
- **No secrets or personal data in prompts.** Only `.env.example` values are shared with tools;
  real secrets stay in git-ignored files.
- **Record uncertainty.** Risk ratings are marked as estimates until execution data exists.

AI assistance does not guarantee correctness or production readiness. Responsibility for every
claim in this repository stays with the author.
