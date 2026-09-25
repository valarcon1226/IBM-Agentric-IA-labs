# Risk Analysis — Docker Compose Production Lab

**Analysis date:** 2026-09-24
**Basis:** source review of `docker-compose.yml`, `init-db.sql`, `backend/src/` and
`docker compose config` validation. The full stack has **not** been started yet, so
runtime behaviour is inferred from the code, not observed.

Status values: **Observed, open** = defect confirmed in the code, fix pending ·
**Observed → fixed** = defect confirmed and corrected · Open = risk without a confirmed defect.

| Risk ID | Risk | Prob. | Impact | Priority | Status | Evidence (file:line) | Fix |
| ------- | ---- | ----- | ------ | -------- | ------ | -------------------- | --- |
| DL-R01 | `/health` reports the database as up without checking it. | High | High | Critical | **Observed, open** | `backend/src/main.py:39-45` — `check_db_connection` only logs `"Mock checking DB connection"` and returns `True`. | T12 |
| DL-R02 | The Docker healthcheck of `fastapi-gateway` can never fail. | High | High | Critical | **Observed, open** | `backend/src/main.py:102-104` returns HTTP 200 with `"status": "degraded"`; `docker-compose.yml:130` uses `curl -f`, which only fails on HTTP ≥ 400. Traefik keeps routing to a broken gateway. | T12 |
| DL-R03 | The API signs tokens with a public default secret. | High | High | Critical | **Observed, open** | `docker-compose.yml:110` passes `JWT_SECRET_FILE`, but `backend/src/config.py:15` has no such field and defaults `JWT_SECRET` to `"insecure-default-secret-change-in-production"`. The Docker secret is mounted and ignored. | T12 |
| DL-R04 | Database role passwords are committed in plaintext. | High | High | Critical | **Observed, open** | `init-db.sql:8,13,18` and `docker-compose.yml:108,146,197,280` (`fastapi_secure_pass`, `n8n_secure_pass`, `grafana_secure_pass`). Anyone with repo access knows them; `secrets/` only protects the superuser. | T11 |
| DL-R05 | The API starts without a real database configured. | Medium | Medium | High | **Observed, open** | `backend/src/config.py:12` defaults `DATABASE_URL` to `sqlite+aiosqlite:///./test.db`; `aiosqlite` is not in `requirements.txt`, so a missing variable fails late and confusingly instead of at startup. | T12 |
| DL-R06 | Redis healthcheck always fails because Redis requires a password. | High | High | Critical | **Observed → fixed** | `redis-cli ping` without `-a` got `NOAUTH`; now `redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning ping \| grep -q PONG`. | done |
| DL-R07 | MinIO never becomes healthy, blocking dependants. | High | High | Critical | **Observed → fixed** | Healthcheck used `curl`, not shipped in current `minio/minio` images; now `mc ready local`. | done |
| DL-R08 | README documents a different stack than the one deployed. | High | Medium | High | **Observed → fixed** | README said `POSTGRES_USER: admin`, `core.celery_app`, `grafana-enterprise`. Sections 6–8 are now verbatim copies; T11 adds `scripts/sync_readme.py --check` and T12 runs it in CI. | done / T11–T12 |
| DL-R09 | Making settings mandatory breaks the Celery worker/beat. | Medium | High | High | Open (design constraint) | `backend/src/celery_app.py` imports `Settings`; `celery-beat` has no `DATABASE_URL` and neither worker has a JWT secret. Requirements must be enforced only at API startup (`require_api_settings`), never in `Settings`. | T12 |
| DL-R10 | Nothing proves the backend works. | High | Medium | High | **Observed, open** | `backend/` has no tests and is not in CI. | T12 |
| DL-R11 | The full stack has never been started. | High | High | Critical | Open | No run of `docker compose up` has been recorded; see `EXECUTION_PLAN.md` sections 3–5. | after T11–T12 |

## Notes for whoever fixes these

- **DL-R01/R02 go together:** a real DB check that keeps answering 200 still leaves the
  healthcheck blind. `/health` must return **503** when any dependency is down.
- **DL-R03:** read `JWT_SECRET_FILE` when `JWT_SECRET` is empty; do not keep any default value.
- **DL-R04:** after changing passwords, an existing postgres volume keeps the old ones
  (`init-db.sh` only runs on an empty volume). Local reset: `docker compose down -v`, which
  deletes all data.
- The exact code and verification for each fix are in
  [`../../docs/tasks/T11-p10-passwords-fuera-del-codigo.md`](../../docs/tasks/T11-p10-passwords-fuera-del-codigo.md)
  and [`../../docs/tasks/T12-p10-backend-health-real-y-ci.md`](../../docs/tasks/T12-p10-backend-health-real-y-ci.md).
  Update the Status column here when each one is done.
