# Project: Data Cleaning & Transformation API

## Current status (2026-09-24)

| Capability                                        | Status          |
| ------------------------------------------------- | --------------- |
| Synchronous CSV cleaning (`/clean` < threshold)   | Working, tested |
| Pandera validation against built-in schema        | Working, tested |
| Size-based routing of large files to Celery       | Working, tested |
| Health check (DB + Redis, 200/503)                | Working, tested |
| API-key authentication on `/api/v1/*`             | Working, tested |
| Clear 400s for unparseable files; no internal details in 500s | Working, tested |
| Async job status and result retrieval             | **Stubbed** — job state is not persisted yet |
| User-defined schemas usable in `/validate`        | **Not yet** — schemas are kept in memory only |
| Excel / JSON input                                | **Not yet** — CSV only |

**Evidence:** 27 passing tests, 58% line coverage, `ruff` + `mypy` clean, run in CI on every push.
Risks and scenario coverage: [`docs/RISK-ANALYSIS.md`](docs/RISK-ANALYSIS.md) ·
[`docs/TRACEABILITY-MATRIX.md`](docs/TRACEABILITY-MATRIX.md).

Sections 1–3 describe the **target design**. Sections 4–8 document the code as it is today.

## 1. Problem Statement
Many automation workflows (e.g., n8n, Zapier) lack robust, heavy-duty data processing capabilities. Passing large datasets through native nodes is slow, memory-intensive, and error-prone. These workflows often fail when attempting to process files containing hundreds of thousands of rows or when applying complex transformations, schema validations, and data enrichments.

This project provides a robust, scalable REST API that acts as a dedicated data processing backend. It receives dirty data (CSV, Excel, JSON), applies rigorous cleaning, validates against predefined schemas, executes complex transformations, and returns production-ready datasets. By offloading this heavy lifting to a specialized microservice, orchestrators can remain lightweight and focus purely on routing and integration logic.

## 2. Architecture
The system follows a microservices architecture centered around FastAPI, with asynchronous background processing for large datasets to ensure the API remains responsive.

```mermaid
flowchart TD
    Client[Client / Orchestrator] -->|HTTP POST| FastAPI[FastAPI App]
    FastAPI -->|Small file < 5MB| Sync[Sync Processing: Pandas]
    FastAPI -->|Large file >= 5MB| Async[Async Queue: Celery]
    
    Async --> Redis[(Redis Broker)]
    Redis --> Worker[Celery Worker]
    Worker -->|Heavy Processing| Sync
    
    Sync --> Validation[Pandera Validation]
    Validation --> MinIO[(MinIO Storage)]
    Validation --> Postgres[(PostgreSQL DB)]
    
    MinIO -->|Returns Data URL| FastAPI
    Postgres -->|Job Metadata| FastAPI
    Worker -->|Updates Status| Postgres
    
    FastAPI -->|HTTP Response| Client
```

- **API Layer**: FastAPI handles synchronous requests and orchestrates async jobs.
- **Processing Engine**: Pandas for vector-based data manipulation. Polars is deferred — add it only for a specific endpoint once profiling shows Pandas is measurably too slow for it; don't wire both from day one.
- **Validation Engine**: Pandera for robust schema enforcement.
- **Storage**: MinIO (S3-compatible) for file storage.
- **Queue/Worker**: Celery and Redis manage the queue for heavy files.
- **Database**: PostgreSQL for metadata, job tracking, and schemas.

## 3. Tech Stack
- **Framework**: FastAPI + Pydantic v2
- **Data Processing**: Pandas, Pandera (Polars deferred — see Architecture note above)
- **Task Queue**: Celery + Redis
- **Database**: PostgreSQL
- **Storage**: MinIO
- **Testing**: Pytest, httpx
- **Containerization**: Docker & Docker Compose

## 4. Environment Variables
Copy `.env.example` to `.env`. Contents (checked against `Settings` by `tests/test_config.py`); `MAX_SYNC_SIZE_MB` is optional (default 5):

```ini
# Database Configuration
# Format: postgresql://user:password@host:port/dbname
DATABASE_URL=postgresql://postgres:postgres@db:5432/data_cleaning_db

# Redis Configuration
# Format: redis://host:port/db
REDIS_URL=redis://redis:6379/0

# MinIO (S3) Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET=data-cleaning-api

# API Settings
DEBUG=true
ENVIRONMENT=development
API_V1_STR=/api/v1
PROJECT_NAME="Data Cleaning & Transformation API"

# Security (required by app.core.config — replace in any real deployment)
JWT_SECRET=change-me
API_KEY=change-me
```

## 5. Database Schema
Applied by `init-db.sql` (mounted into the `db` container). The tables exist today; the API does
not read or write them yet — see "Current status" (jobs and schemas are still in memory).

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE schemas (
    schema_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    definition JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- SET NULL, not CASCADE: deleting a schema must not erase job history.
    schema_id UUID REFERENCES schemas(schema_id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',  -- PENDING | PROCESSING | COMPLETED | FAILED
    operation_type VARCHAR(50) NOT NULL,
    input_file_path VARCHAR(512),
    output_file_path VARCHAR(512),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_jobs_schema_id ON jobs(schema_id);
CREATE INDEX idx_schemas_name ON schemas(name);
```

## 6. API Endpoints

Every `/api/v1/*` endpoint requires `Authorization: Bearer <API_KEY>` (value from `.env`);
a missing or wrong key returns `401`. `/health`, `/` and `/metrics` are public.

Examples below are the **current** request/response contract. The transform and enrich bodies
are asserted verbatim by `tests/test_api.py`, so the suite fails if they drift.

Errors: `400` bad input (invalid options JSON, unparseable file), `401` auth, `404` unknown
schema/job, `422` body does not match the schema, `500` returns only
`"Internal processing error"` (details go to the server log).

### 6.1 POST /api/v1/clean
Cleans a CSV. Files under `MAX_SYNC_SIZE_MB` (default 5) are cleaned inline; larger files are
stored in MinIO and queued to Celery.

`options` keys (all optional): `remove_empty_rows` (default `true`), `remove_empty_cols`
(default `true`), `remove_duplicates` (default `false`), `handle_nulls` (`drop` | `fill_value` |
`interpolate`), `null_fill_value` (used with `fill_value`, default `"Unknown"`),
`trim_whitespace` (default `true`), `normalize_lowercase` (default `false`).

```bash
curl -X POST "http://localhost:8000/api/v1/clean" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@dirty.csv" \
  -F 'options={"remove_duplicates": true, "handle_nulls": "fill_value", "null_fill_value": 0}'
```
**Response (small file):**
```json
{"status": "success", "data": [{"name": "Ana", "age": 30}, {"name": "Luis", "age": 0}]}
```
**Response (large file):**
```json
{"status": "processing", "job_id": "3f1c9a52-8b0e-4d2a-9c7e-5a1b2c3d4e5f"}
```

### 6.2 POST /api/v1/validate
Validates inline rows against a schema. Today only the built-in `user_schema`
(`id: int`, `name: str`, `age: int >= 0`) is available.
```bash
curl -X POST "http://localhost:8000/api/v1/validate" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"schema_id": "user_schema", "data": [{"id": 1, "name": "Ana", "age": -5}]}'
```
**Response:**
```json
{
  "status": "invalid",
  "errors": [{"schema_context": "Column", "column": "age",
              "check": "greater_than_or_equal_to(0)", "check_number": 0,
              "failure_case": -5, "index": 0}]
}
```
Valid data returns `{"status": "valid"}`.

### 6.3 POST /api/v1/transform
Queues a transformation of a file previously stored via `/upload`.
`operation`: `pivot` | `melt` | `merge` | `split` | `aggregate`; `params` are that operation's
arguments (see `app/services/transformer.py`).
```bash
curl -X POST "http://localhost:8000/api/v1/transform" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "uploads/1234-5678_dataset.csv", "operation": "pivot",
       "params": {"index": "date", "columns": "category", "values": "revenue"}}'
```
**Response:**
```json
{"status": "processing", "job_id": "7890abcd-1234-4ef5-8a6b-7c8d9e0f1a2b"}
```

### 6.4 POST /api/v1/enrich
Queues enrichment of a stored file. `operations` ⊂ `validate_emails`, `normalize_phones`;
`target_columns` maps `email` / `phone` to column names in the file.
```bash
curl -X POST "http://localhost:8000/api/v1/enrich" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "uploads/1234-5678_contacts.csv",
       "operations": ["validate_emails", "normalize_phones"],
       "target_columns": {"email": "email_col", "phone": "phone_col"}}'
```
**Response:**
```json
{"status": "processing", "job_id": "abcd1234-5678-4ef9-8a0b-1c2d3e4f5a6b"}
```

### 6.5 POST /api/v1/upload
Stores a file in MinIO. Use the returned `file_url` as `file_path` in transform/enrich.
```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@massive_dataset.csv"
```
**Response:**
```json
{"status": "success", "file_url": "uploads/1234-5678_massive_dataset.csv", "size": 104857600}
```

### 6.6 GET /api/v1/jobs/{job_id} — *stub*
Job state is not persisted yet (DC-R04), so this returns `{"job_id": "...", "status": "UNKNOWN"}`
for real job ids. Target: read the `jobs` table.

### 6.7 GET /api/v1/jobs/{job_id}/result — *stub*
Returns `404` for unknown jobs, `400` for jobs not `COMPLETED`, otherwise
`{"job_id": "...", "download_url": "<presigned MinIO URL>"}`. Same limitation as 6.6.

### 6.8 POST /api/v1/schemas — *in memory*
```bash
curl -X POST "http://localhost:8000/api/v1/schemas" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "customers", "fields": {"id": "int", "email": "str"}}'
```
**Response:**
```json
{"status": "success", "schema_id": "sch_a75301b1",
 "data": {"id": "sch_a75301b1", "name": "customers", "fields": {"id": "int", "email": "str"}}}
```
Stored schemas are lost on restart and cannot yet be used by `/validate` (DC-R07).

### 6.9 GET /api/v1/schemas — *in memory*
```bash
curl "http://localhost:8000/api/v1/schemas" -H "Authorization: Bearer $API_KEY"
```
**Response:**
```json
{"status": "success", "schemas": [{"id": "sch_a75301b1", "name": "customers",
                                   "fields": {"id": "int", "email": "str"}}]}
```

## 7. Docker Services
Defined in `docker-compose.yml`. All services read `.env` (copy `.env.example`).

| Service  | Image / build           | Ports      | Healthcheck                  | Depends on (healthy) |
| -------- | ----------------------- | ---------- | ---------------------------- | -------------------- |
| `api`    | `build: .`              | 8000       | —                            | db, redis, minio     |
| `worker` | `build: .`, `celery -A app.core.worker worker` | — | —               | db, redis, minio     |
| `db`     | `postgres:16-alpine`, runs `init-db.sql` | 5432 | `pg_isready -U postgres -d data_cleaning_db` | — |
| `redis`  | `redis:7-alpine`        | 6379       | `redis-cli ping`             | —                    |
| `minio`  | `minio/minio`           | 9000, 9001 | `mc ready local`             | —                    |

## 8. File Structure
```
04-data-cleaning-api/
├── app/
│   ├── api/routes/        clean, validate, transform, enrich, upload, jobs, schemas
│   ├── core/              config.py (typed settings), database.py, security.py (API key), worker.py (Celery)
│   ├── models/            db.py (ORM), domain.py
│   ├── services/          cleaner, transformer, enricher, storage (MinIO), tasks (Celery tasks)
│   └── main.py            app, router registration, /health
├── tests/
│   ├── conftest.py        inert settings for tests
│   ├── test_api.py        tests against the real app.main:app
│   ├── test_cleaner.py
│   └── test_config.py     .env.example ↔ Settings contract
├── docs/                  RISK-ANALYSIS.md, TRACEABILITY-MATRIX.md
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── init-db.sql
├── pyproject.toml         ruff, mypy, pytest config
├── requirements.txt
└── requirements-dev.txt
```

## 9. Implementation Steps
1. **Repo skeleton** — create the directory tree matching section 8. *Verify:* Directory listing is accurate.
2. **Minimal infra up** — Start `db`, `redis`, `minio` in `docker-compose.yml` to ensure backing services run locally. *Verify:* `docker compose up -d db redis minio` succeeds.
3. **Database Schema Setup** — Apply the tables from section 5 via a plain SQL initialization script mounted into the Postgres container. *Verify:* `\dt` lists `schemas` and `jobs`.
4. **Core Processing Logic** — Implement `services/cleaner.py`, `services/transformer.py`, and `services/enricher.py` using Pandas. Emphasize unit testing with mock DataFrames before wiring the API. *Verify:* `pytest tests/test_cleaner.py` passes.
5. **Pandera Schema Validation** — Define generic schema translation from JSON (stored in DB) to Pandera classes in `services/validator.py`. Implement the `/schemas` and `/validate` routes.
6. **Celery Worker Integration** — Configure `app/core/worker.py` and route heavy tasks (>5MB) to Celery. Ensure the worker updates the `jobs` table `status`, `started_at`, and `completed_at` timestamps. 
7. **Storage Wiring** — Implement `services/storage.py` using `boto3` or `minio-py` to handle multipart uploads, downloads, and presigned URLs.
8. **Routing Completeness** — Wire all routes in `app/api/routes/` as detailed in section 6. Make sure synchronous processing is still supported for small payloads.
9. **Full Stack Test** — `docker compose up -d`. Upload a large CSV to `/upload`, trigger an async `/clean` job, poll `/jobs/{id}`, and download via `/jobs/{id}/result`.

## 10. Testing Strategy
1. **Unit tests (Pandas/Pandera):** Fast, in-memory testing of data manipulation functions. No DB/network dependencies.
2. **API Endpoint tests:** Pytest with `TestClient` or `httpx` to mock Redis/MinIO and test FastAPI validation and response schemas.
3. **Integration tests:** End-to-end testing requiring Docker Compose services up. E.g., submitting a real CSV file and asserting the final output in MinIO. *(Planned — not implemented yet.)*

API tests import the real `app.main:app`, not a test-only FastAPI instance, so a route missing
from the production app fails the suite. `tests/conftest.py` supplies inert settings; no test
opens a network connection.

Run locally (same gates as CI):

```bash
pip install -r requirements-dev.txt
ruff check app tests && ruff format --check app tests
mypy app
pytest --cov
```
