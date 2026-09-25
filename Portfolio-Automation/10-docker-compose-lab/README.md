# Project: Docker Compose Production Lab

> **Status (2026-09-24):** scaffolded, not yet run end to end. Known defects and their fixes are
> tracked in [`docs/RISK-ANALYSIS.md`](docs/RISK-ANALYSIS.md) — four are Critical and open
> (fake DB health check, healthcheck that cannot fail, ignored JWT secret, committed passwords).

## 1. Problem Statement
Deploying a complex ecosystem of microservices, databases, and background workers requires a robust, reproducible, and secure infrastructure. A single failure in a database or worker node can cascade into systemic failure. This project establishes a production-grade container orchestration setup using Docker Compose to host the entire portfolio stack—ensuring high availability, secure networking, persistent storage, and automated routing with SSL termination.

## 2. Architecture
```mermaid
flowchart TD
    Internet((Internet)) -->|HTTPS/443| Traefik[Traefik Reverse Proxy]
    
    subgraph Frontend Network
        Traefik -->|api.example.com| FastAPI[FastAPI Gateway]
        Traefik -->|n8n.example.com| n8n[n8n Workflow Engine]
        Traefik -->|grafana.example.com| Grafana[Grafana Dashboards]
    end
    
    subgraph Backend Network
        FastAPI --> CeleryWorker[Celery Worker]
        FastAPI --> CeleryBeat[Celery Beat]
    end
    
    subgraph Database Network
        FastAPI --> Postgres[(PostgreSQL)]
        n8n --> Postgres
        FastAPI --> Redis[(Redis)]
        CeleryWorker --> Redis
        CeleryBeat --> Redis
        FastAPI --> Minio[(MinIO Object Storage)]
    end
    
    Prometheus[Prometheus] -.->|Scrapes| FastAPI
    Prometheus -.->|Scrapes| Postgres
```

## 3. Tech Stack
*   **Orchestration:** Docker, Docker Compose
*   **Routing & SSL:** Traefik, Let's Encrypt (ACME)
*   **Core Services:** n8n, FastAPI (Python 3.12)
*   **Databases & Brokers:** PostgreSQL 16, Redis 7, MinIO
*   **Background Tasks:** Celery, Celery Beat
*   **Observability:** Prometheus, Grafana
*   **OS/Security:** Ubuntu 22.04 LTS, UFW, Fail2ban

## 4. File Structure
```
.
├── backend/
│   ├── src/
│   ├── Dockerfile
│   └── requirements.txt
├── letsencrypt/
│   └── acme.json          (created at runtime, git-ignored)
├── secrets/
│   ├── db_password.txt    (git-ignored, create locally)
│   └── jwt_secret.txt     (git-ignored, create locally)
├── .env.example
├── docker-compose.yml
├── init-db.sh
├── prometheus.yml
├── scripts/
│   └── sync_readme.py     (keeps README sections 6–8 in sync; `--check` runs in CI)
├── docs/
│   └── RISK-ANALYSIS.md
└── README.md
```

## 5. Docker Services List
Only Traefik publishes host ports (80/443). Every other port below is internal to the Docker
networks and reached through Traefik routes or service names.

| Service | Role | Internal port | Healthcheck |
| --- | --- | --- | --- |
| `traefik` | Edge router, TLS via Let's Encrypt | 80, 443 (published) | `traefik healthcheck --ping` |
| `postgres` | Shared PostgreSQL 16 (runs `init-db.sh`) | 5432 | `pg_isready -U postgres` |
| `redis` | Cache + Celery broker (password protected) | 6379 | `redis-cli -a $REDIS_PASSWORD ping` |
| `fastapi-gateway` | Main API (`backend/`) | 8000 | `curl -f /health` |
| `celery-worker` | Task processing | — | `celery -A src.celery_app inspect ping` |
| `celery-beat` | Periodic task scheduling | — | — |
| `n8n` | Workflow engine | 5678 | `wget /healthz` |
| `minio` | S3-compatible storage | 9000 / 9001 | `mc ready local` |
| `prometheus` | Metrics | 9090 | `wget /-/healthy` |
| `grafana` | Dashboards | 3000 | `wget /api/health` |

## 6. Environment Variables (.env.example)
Verbatim copy of `.env.example`. The postgres superuser password is **not** read from
`.env`: it comes from the Docker secret `secrets/db_password.txt` (`POSTGRES_PASSWORD_FILE`).

```env
# =============================================================================
# Docker Compose Production Lab — Environment Variables
# Copy this file to .env and fill in your values
# =============================================================================

# --- Database (PostgreSQL 16) ---
DB_PASSWORD=change_me_to_a_strong_password
# Per-service database roles (created by init-db.sh). Letters and digits only:
# they are embedded in connection URLs.
FASTAPI_DB_PASSWORD=change_me_fastapi
N8N_DB_PASSWORD=change_me_n8n
GRAFANA_DB_PASSWORD=change_me_grafana

# --- Redis 7 ---
REDIS_PASSWORD=change_me_to_a_strong_password

# --- JWT Authentication ---
JWT_SECRET=change_me_to_a_random_256bit_string

# --- Domains (point DNS A records to your VPS IP) ---
API_DOMAIN=api.example.com
N8N_DOMAIN=n8n.example.com
GRAFANA_DOMAIN=grafana.example.com
ACME_EMAIL=admin@example.com

# --- MinIO (S3-compatible object storage) ---
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=change_me_to_a_strong_password

# --- Grafana ---
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=change_me
```

## 7. docker-compose.yml (Complete)
Verbatim copy of `docker-compose.yml` (regenerate with `py -3 scripts/sync_readme.py`).

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt

volumes:
  postgres_data:
  redis_data:
  minio_data:
  grafana_data:
  prometheus_data:
  n8n_data:
  letsencrypt:

networks:
  frontend_net:
  backend_net:
  db_net:

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=false"
      - "--ping=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entryPoint.to=websecure"
      - "--entrypoints.web.http.redirections.entryPoint.scheme=https"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
      - "--metrics.prometheus=true"
      - "--metrics.prometheus.buckets=0.1,0.3,1.2,5.0"
      - "--entrypoints.metrics.address=:8082"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt
    networks:
      - frontend_net
      - backend_net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "traefik", "healthcheck", "--ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      FASTAPI_DB_PASSWORD: ${FASTAPI_DB_PASSWORD}
      N8N_DB_PASSWORD: ${N8N_DB_PASSWORD}
      GRAFANA_DB_PASSWORD: ${GRAFANA_DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sh:/docker-entrypoint-initdb.d/init-db.sh:ro
    secrets:
      - db_password
    networks:
      - db_net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - db_net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a \"${REDIS_PASSWORD}\" --no-auth-warning ping | grep -q PONG"]
      interval: 10s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  fastapi-gateway:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql://fastapi_user:${FASTAPI_DB_PASSWORD}@postgres:5432/fastapi_db
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - JWT_SECRET_FILE=/run/secrets/jwt_secret
    secrets:
      - jwt_secret
    networks:
      - frontend_net
      - backend_net
      - db_net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.fastapi.rule=Host(`${API_DOMAIN}`)"
      - "traefik.http.routers.fastapi.entrypoints=websecure"
      - "traefik.http.routers.fastapi.tls.certresolver=myresolver"
      - "traefik.http.services.fastapi.loadbalancer.server.port=8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: ["celery", "-A", "src.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
    environment:
      - DATABASE_URL=postgresql://fastapi_user:${FASTAPI_DB_PASSWORD}@postgres:5432/fastapi_db
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
    networks:
      - backend_net
      - db_net
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "celery -A src.celery_app inspect ping --timeout 10 || exit 1"]
      interval: 60s
      timeout: 15s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: ["celery", "-A", "src.celery_app", "beat", "--loglevel=info"]
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
    networks:
      - backend_net
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  n8n:
    image: docker.n8n.io/n8nio/n8n
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n_db
      - DB_POSTGRESDB_USER=n8n_user
      - DB_POSTGRESDB_PASSWORD=${N8N_DB_PASSWORD}
      - N8N_HOST=${N8N_DOMAIN}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - NODE_ENV=production
      - WEBHOOK_URL=https://${N8N_DOMAIN}/
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - frontend_net
      - backend_net
      - db_net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`${N8N_DOMAIN}`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls.certresolver=myresolver"
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:5678/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${MINIO_ROOT_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
      - MINIO_PROMETHEUS_AUTH_TYPE=public
    volumes:
      - minio_data:/data
    networks:
      - backend_net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - backend_net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  grafana:
    image: grafana/grafana
    environment:
      - GF_SECURITY_ADMIN_USER=${GF_SECURITY_ADMIN_USER}
      - GF_SECURITY_ADMIN_PASSWORD=${GF_SECURITY_ADMIN_PASSWORD}
      - GF_DATABASE_TYPE=postgres
      - GF_DATABASE_HOST=postgres:5432
      - GF_DATABASE_NAME=grafana_db
      - GF_DATABASE_USER=grafana_user
      - GF_DATABASE_PASSWORD=${GRAFANA_DB_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    networks:
      - frontend_net
      - backend_net
      - db_net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=Host(`${GRAFANA_DOMAIN}`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.routers.grafana.tls.certresolver=myresolver"
    depends_on:
      postgres:
        condition: service_healthy
      prometheus:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

## 8. Database Initialization (init-db.sh)
Verbatim copy of `init-db.sh`. Role passwords come from the environment.

```bash
#!/bin/bash
# Runs once, on the first start of the postgres container (docker-entrypoint-initdb.d).
# Creates one database + owner role per service. Passwords come from the environment
# (see .env.example); nothing secret is stored in this file.
set -eo pipefail

: "${FASTAPI_DB_PASSWORD:?FASTAPI_DB_PASSWORD is required}"
: "${N8N_DB_PASSWORD:?N8N_DB_PASSWORD is required}"
: "${GRAFANA_DB_PASSWORD:?GRAFANA_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v fastapi_pw="$FASTAPI_DB_PASSWORD" \
  -v n8n_pw="$N8N_DB_PASSWORD" \
  -v grafana_pw="$GRAFANA_DB_PASSWORD" <<'EOSQL'
CREATE USER fastapi_user WITH PASSWORD :'fastapi_pw';
CREATE DATABASE fastapi_db OWNER fastapi_user;
GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO fastapi_user;

CREATE USER n8n_user WITH PASSWORD :'n8n_pw';
CREATE DATABASE n8n_db OWNER n8n_user;
GRANT ALL PRIVILEGES ON DATABASE n8n_db TO n8n_user;

CREATE USER grafana_user WITH PASSWORD :'grafana_pw';
CREATE DATABASE grafana_db OWNER grafana_user;
GRANT ALL PRIVILEGES ON DATABASE grafana_db TO grafana_user;

\c fastapi_db
GRANT ALL ON SCHEMA public TO fastapi_user;

\c n8n_db
GRANT ALL ON SCHEMA public TO n8n_user;

\c grafana_db
GRANT ALL ON SCHEMA public TO grafana_user;
EOSQL
```

## 9. Implementation Steps

**Step 0 — Consolidation strategy:** Projects `01`-`09`, `11`, `12` ship standalone compose files for local development. This project merges them into **one production topology** with **one shared Postgres instance** and **one shared Redis instance** (partitioned by logical DB number). 

1. **Server provisioning:** Spin up an Ubuntu 22.04 LTS VPS. *Verify:* `ssh` access works and `docker --version` / `docker compose version` succeed.
2. **Directory + secrets setup:** Clone repo, run `mkdir -p secrets letsencrypt`, and populate `.env` and `secrets/`.
3. **Consolidated Postgres schema:** Write one `init-db.sh` that creates one database and role per service, reading passwords from the environment.
4. **Network & DNS:** Point DNS A records for `api.`, `n8n.`, and `grafana.` to the VPS IP.
5. **Launch:** Run `docker compose up -d`. *Verify:* `docker compose ps` shows services as healthy/running.
6. **Verification:** Confirm Traefik acquired Let's Encrypt certificates. *Verify:* `curl -I https://api.example.com` returns valid TLS handshake.

## 10. Operational Documentation
### DEPLOY.md
1. **Initial server setup:** Create `deploy` user, configure SSH keys, disable root login.
2. **Install Docker:** Add GPG key, install `docker-ce`.
3. **Configure UFW:** `ufw allow 22, 80, 443/tcp`.
4. **Install Fail2ban:** Setup ssh jails.

### SECURITY.md
* **Secrets Management:** Docker secrets and environment variables.
* **Network Isolation:** DB services are completely isolated from `frontend_net`.

### BACKUP.md
* **Strategy:** Nightly `pg_dump`. Replicated to MinIO container.

### TROUBLESHOOTING.md
* **Traefik 404s:** Verify labels and DNS.
* **DB Connection Issues:** Check `db_net` attachment and healthchecks.

