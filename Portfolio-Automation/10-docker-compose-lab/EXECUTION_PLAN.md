# Execution Plan — Docker Compose Production Lab

Source of truth: `docker-compose.yml`, `init-db.sql`, `backend/` (the code already exists).
`README.md` sections 6–8 are verbatim copies of those files; update them together.

This is a **verify-and-close** plan for existing code, not a greenfield build. Build it last
(see `../docs/BUILD-PLAN.md`): it consolidates the other services once they work on their own.

## Prerequisites
- Docker + Docker Compose v2
- For TLS: a VPS with DNS A records for `API_DOMAIN`, `N8N_DOMAIN`, `GRAFANA_DOMAIN`
- `cp .env.example .env` and fill in real values
- `secrets/db_password.txt` and `secrets/jwt_secret.txt` created locally (git-ignored)

## Checklist

### 1. Configuration validity
- [ ] Compose file renders with the example environment.
  - Verify: `docker compose --env-file .env.example config -q` → exit code 0, no warnings.

### 2. Remove hardcoded service passwords (security — do before any deploy)
Today `init-db.sql` and `docker-compose.yml` contain plaintext passwords for `fastapi_user`,
`n8n_user` and `grafana_user` (`*_secure_pass`).
- [ ] Replace `init-db.sql` with `init-db.sh` that reads `FASTAPI_DB_PASSWORD`, `N8N_DB_PASSWORD`,
  `GRAFANA_DB_PASSWORD` from the environment (or `/run/secrets/*`) and runs the same SQL via `psql`.
- [ ] Reference those variables in the `fastapi-gateway`, `celery-*`, `n8n` and `grafana` services
  instead of literals; add them to `.env.example` with `change_me` values.
  - Verify: `Select-String -Path docker-compose.yml, init-db.* -Pattern "_secure_pass"` → no matches.
  - Verify: README sections 6–8 regenerated from the new files.

### 3. Data layer
- [ ] `docker compose up -d postgres redis` → both `healthy`.
  - Verify: `docker compose ps` shows `(healthy)` for both within 60 s.
- [ ] Init script created the three databases and roles.
  - Verify: `docker compose exec postgres psql -U postgres -c "\l"` lists `fastapi_db`, `n8n_db`, `grafana_db`.
- [ ] Redis requires the password.
  - Verify: `docker compose exec redis redis-cli ping` → `NOAUTH ...`;
    with `-a <password>` → `PONG`.

### 4. Backend
- [ ] Add `backend/tests/` with a test for `/health` (healthy and degraded paths, dependencies mocked)
  following the pattern of `04-data-cleaning-api/tests/`.
  - Verify: `pytest` passes locally; then add `10-docker-compose-lab/backend` support to the
    CI workflow (it uses `src/`, not `app/` — adjust the lint/type-check paths for this project).
- [ ] `docker compose up -d fastapi-gateway celery-worker celery-beat` → all running, gateway healthy.
  - Verify: `docker compose exec fastapi-gateway curl -fs http://localhost:8000/health` → JSON with `"status": "healthy"`.
  - Verify: `docker compose exec celery-worker celery -A src.celery_app inspect ping` → `pong`.

### 5. Edge and platform services
- [ ] `docker compose up -d` (full stack) → every service with a healthcheck reports `healthy`.
  - Verify: `docker compose ps --format "{{.Name}} {{.Status}}"` — no `unhealthy` or `starting` after 2 min.
- [ ] Traefik routes resolve (on the VPS, with real DNS).
  - Verify: `curl -I https://$API_DOMAIN/health` → `200` with a valid certificate.
- [ ] Prometheus scrapes its targets.
  - Verify: `http://<prometheus>/targets` shows every job in `prometheus.yml` as `UP`.

### 6. Operations
- [ ] Walk through `BACKUP.md` once (backup + restore into a scratch database).
  - Verify: restored row counts match the source.
- [ ] Update the root `README.md` status row for project 10 only after steps 1–5 pass.

## Definition of Done
- All checklist items above verified, with command output recorded.
- No plaintext credentials in tracked files.
- README sections 6–8 identical to the files they copy.
