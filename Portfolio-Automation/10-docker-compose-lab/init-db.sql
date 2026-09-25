-- =============================================================================
-- Portfolio Stack — Database Initialization
-- This script runs once on first postgres container startup.
-- It creates isolated databases and users for each service.
-- =============================================================================

-- FastAPI application database
CREATE USER fastapi_user WITH PASSWORD 'fastapi_secure_pass';
CREATE DATABASE fastapi_db OWNER fastapi_user;
GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO fastapi_user;

-- n8n workflow engine database
CREATE USER n8n_user WITH PASSWORD 'n8n_secure_pass';
CREATE DATABASE n8n_db OWNER n8n_user;
GRANT ALL PRIVILEGES ON DATABASE n8n_db TO n8n_user;

-- Grafana dashboards database
CREATE USER grafana_user WITH PASSWORD 'grafana_secure_pass';
CREATE DATABASE grafana_db OWNER grafana_user;
GRANT ALL PRIVILEGES ON DATABASE grafana_db TO grafana_user;

-- Grant schema permissions (required for Postgres 15+)
\c fastapi_db
GRANT ALL ON SCHEMA public TO fastapi_user;

\c n8n_db
GRANT ALL ON SCHEMA public TO n8n_user;

\c grafana_db
GRANT ALL ON SCHEMA public TO grafana_user;
