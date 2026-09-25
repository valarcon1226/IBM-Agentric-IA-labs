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
