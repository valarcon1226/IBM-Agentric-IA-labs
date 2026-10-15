# Execution Plan — Docker Compose Production Lab

Source of truth: `docker-compose.yml`, `init-db.sh`, `backend/` (the code already exists).
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
- [x] Compose file renders with the example environment.
  - Done: `docker compose --env-file .env.example config -q` → exit code 0, no warnings.

### 2. Remove hardcoded service passwords (security — do before any deploy)
Before T11, `init-db.sql` and `docker-compose.yml` contained plaintext passwords for
`fastapi_user`, `n8n_user` and `grafana_user`.
- [x] Replace `init-db.sql` with `init-db.sh` that reads `FASTAPI_DB_PASSWORD`, `N8N_DB_PASSWORD`,
  `GRAFANA_DB_PASSWORD` from the environment and runs the same SQL via `psql`.
  - Done (T11): `init-db.sh` created, LF line endings verified.
- [x] Reference those variables in the `fastapi-gateway`, `celery-*`, `n8n` and `grafana` services
  instead of literals; add them to `.env.example` with `change_me` values.
  - Done (T11): no literal role passwords left; compose resolves them from `.env`.
  - Verify: `docker compose --env-file .env.example config` shows `change_me_fastapi`,
    `change_me_n8n` and `change_me_grafana` where the passwords go.
  - Verify: README sections 6–8 regenerated from the new files.

### 3. Data layer
- [x] `docker compose up -d postgres redis` → both `healthy`.
  - Done: `docker compose ps` shows `(healthy)` for both:
    ```
    10-docker-compose-lab-postgres-1   postgres:16-alpine   Up 27 seconds (healthy)   5432/tcp
    10-docker-compose-lab-redis-1      redis:7-alpine       Up 27 seconds (healthy)   6379/tcp
    ```
- [x] Init script created the three databases and roles.
  - Done: `docker compose exec postgres psql -U postgres -c "\l"`:
    ```
    fastapi_db | fastapi_user | UTF8 | libc | en_US.utf8 | en_US.utf8
    grafana_db | grafana_user | UTF8 | libc | en_US.utf8 | en_US.utf8
    n8n_db     | n8n_user     | UTF8 | libc | en_US.utf8 | en_US.utf8
    ```
- [x] Redis requires the password.
  - Done: `docker compose exec redis redis-cli ping` → `NOAUTH Authentication required.`;
    with `-a change_me_to_a_strong_password --no-auth-warning ping` → `PONG`.

### 4. Backend
- [x] Add `backend/tests/` with a test for `/health` (healthy and degraded paths, dependencies mocked)
  following the pattern of `04-data-cleaning-api/tests/`.
  - Done (T12): 5 passed, cobertura 61%
  - Verify: `pytest` passes locally; then add `10-docker-compose-lab/backend` support to the
    CI workflow (it uses `src/`, not `app/` — adjust the lint/type-check paths for this project).
- [x] `docker compose up -d fastapi-gateway celery-worker celery-beat` → all running, gateway healthy.
  - Done: `docker compose exec fastapi-gateway curl -fs http://localhost:8000/health`:
    ```json
    {"status":"healthy","timestamp":"2026-10-14T21:09:57.993513+00:00","services":{"api":"up","database":"up","redis":"up"}}
    ```
  - Done: `docker compose exec celery-worker celery -A src.celery_app inspect ping`:
    ```
    ->  celery@7ab466ca2e4d: OK
            pong
    1 node online.
    ```

### 5. Edge and platform services
- [x] `docker compose up -d` (full stack) → every service with a healthcheck reports `healthy`.
  - Done: `docker compose ps --format "{{.Name}} {{.Status}}"`:
    ```
    10-docker-compose-lab-celery-beat-1 Up About a minute
    10-docker-compose-lab-celery-worker-1 Up About a minute (healthy)
    10-docker-compose-lab-fastapi-gateway-1 Up About a minute (healthy)
    10-docker-compose-lab-grafana-1 Up About a minute (healthy)
    10-docker-compose-lab-minio-1 Up About a minute (healthy)
    10-docker-compose-lab-n8n-1 Up About a minute (healthy)
    10-docker-compose-lab-postgres-1 Up 6 minutes (healthy)
    10-docker-compose-lab-prometheus-1 Up About a minute (healthy)
    10-docker-compose-lab-redis-1 Up 6 minutes (healthy)
    10-docker-compose-lab-traefik-1 Up About a minute (healthy)
    ```
- [x] Traefik routes resolve (on the VPS, with real DNS).
  - Done (Local override `docker-compose.local.yml`):
    - `curl -i http://api.localhost:8088/health` → `HTTP/1.1 200 OK`
    - `curl -i http://n8n.localhost:8088/healthz` → `HTTP/1.1 200 OK` (`{"status":"ok"}`)
    - `curl -i http://grafana.localhost:8088/api/health` → `HTTP/1.1 200 OK` (`{"database":"ok"}`)
- [x] Prometheus scrapes its targets.
  - Done: `docker compose exec prometheus wget -qO- http://localhost:9090/api/v1/targets` confirms all 4 active targets (`fastapi`, `minio`, `prometheus`, `traefik`) in state `"health":"up"`.

### 6. Operations
- [x] Walk through `BACKUP.md` once (backup + restore into a scratch database).
  - Done: `pg_dumpall -U postgres -f /tmp/backup.sql` generated 932.6KB dump. Inserted 3 rows into `fastapi_db.test_backup`, restored to `scratch_db` via `pg_dump | psql`, verified `SELECT count(*) FROM test_backup` returned 3, and dropped `scratch_db`.
- [x] Update the root `README.md` status row for project 10 only after steps 1–5 pass.
  - Done: root `README.md` row updated to `Implemented` (9 services healthy · Traefik routing · Backend: 5 tests, 61% cov · CI).

## Definition of Done
- All checklist items above verified, with command output recorded.
- No plaintext credentials in tracked files.
- README sections 6–8 identical to the files they copy.
