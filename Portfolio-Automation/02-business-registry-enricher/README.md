# Project: EU Business Registry Enricher

## 1. Problem Statement
Validating B2B leads or onboarding European clients often requires manual verification of company status, directors, and VAT numbers. This project automates the enrichment process by querying official European government registries (Companies House, INSEE, VIES) to return verified business data.

*Note on Spain (BORME):* Spain support is planned, but BORME doesn't have a clean public API yet. VIES is currently used for EU-wide VAT validation which covers Spain.

## 2. Architecture

```mermaid
flowchart LR
    A[Input CSV / API Call / n8n] --> B(FastAPI Gateway)
    B --> C{Country Router}
    C -->|GB| D[Companies House API]
    C -->|FR| E[INSEE SIRENE API]
    C -->|EU| G[VIES VAT Validation]
    D & E & G --> H(Data Normalizer)
    H --> I[(PostgreSQL Cache)]
    I --> J[Enriched Output / Google Sheets]
```

## 3. Tech Stack
- **Orchestrator:** n8n
- **Backend:** FastAPI (API connector layer)
- **Database/Cache:** PostgreSQL
- **Rate Limiting:** `aiolimiter` (in-process async rate limiter — this is a single-instance API, so no Redis-backed distributed limiter is needed)
- **Retries:** `tenacity` (exponential backoff)
- **Infrastructure:** Docker Compose

## 4. Database Schema

```sql
CREATE TABLE company_cache (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    company_identifier VARCHAR(50) NOT NULL,
    company_name VARCHAR(255),
    status VARCHAR(50),
    incorporation_date DATE,
    raw_data JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, company_identifier)
);

CREATE TABLE api_logs (
    log_id SERIAL PRIMARY KEY,
    registry_name VARCHAR(50),
    endpoint VARCHAR(255),
    response_code INT,
    response_time_ms INT,
    error_message TEXT,
    company_identifier VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 5. API Endpoints

### Enrich Multiple Companies
**POST /api/v1/enrich**

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "companies": [
      {"country": "GB", "identifier": "00000006"},
      {"country": "FR", "identifier": "552081317"}
    ]
  }'
```

**Response:**
```json
{
  "results": [
    {
      "country": "GB",
      "identifier": "00000006",
      "company_name": "DEFAULT LIMITED",
      "status": "active",
      "cached": false
    },
    {
      "country": "FR",
      "identifier": "552081317",
      "company_name": "SOCIETE AIR FRANCE",
      "status": "active",
      "cached": true
    }
  ]
}
```

### Enrich Single Company
**GET /api/v1/enrich/{country}/{identifier}?force_refresh=false**

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/enrich/GB/00000006?force_refresh=true" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "country": "GB",
  "identifier": "00000006",
  "company_name": "DEFAULT LIMITED",
  "status": "active",
  "incorporation_date": "1856-11-20",
  "raw_data": {
    "company_status": "active",
    "type": "ltd"
  },
  "cached": false
}
```

## 6. Rate Limiting Strategy & Retries
- **Companies House (UK):** 600 requests per 5 minutes, enforced with an in-process `aiolimiter.AsyncLimiter(600, 300)`.
- **INSEE (FR):** 30 requests per minute, enforced with `aiolimiter.AsyncLimiter(30, 60)`.
- **Why in-process, not Redis:** this API runs as a single instance; a per-process limiter is simpler and sufficient. Only move to a Redis-backed distributed limiter if this is deployed with multiple replicas hitting the same upstream quota.
- **Retry Logic:** `tenacity` exponential backoff (retry on 429 and 5xx errors, up to 5 attempts) wrapping each registry client call.

## 7. Docker Services

| Service | Image/Dockerfile | Ports | Depends On |
|---------|------------------|-------|------------|
| `enricher_api` | `Dockerfile` | 8000:8000 | `postgres` |
| `postgres` | `postgres:15-alpine` | 5432:5432 | - |
| `n8n` | `n8nio/n8n` | 5678:5678 | - |

No `redis` service: rate limiting is in-process (`aiolimiter`), so there is nothing shared across processes to store there.

## 8. File Structure
```text
02-business-registry-enricher/
├── app/
│   ├── main.py
│   ├── registries/
│   │   ├── companies_house.py
│   │   ├── insee.py
│   │   └── vies.py
│   ├── models.py
│   └── database.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## 9. n8n Workflow Description
1. **Webhook / Read File Node:** Receives a CSV file containing country codes and company identifiers.
2. **HTTP Request Node:** Posts the payload as a batch to the FastAPI `/api/v1/enrich` endpoint.
3. **Set/Filter Nodes:** Flattens the enriched JSON response.
4. **Google Sheets / CRM Node:** Writes the validated `company_name`, `status`, and `incorporation_date` back to the tracking system, automatically enriching leads without human intervention.

## 10. Implementation Steps
1. **Repo skeleton + infra** — create the tree from section 8; `docker-compose.yml` with only `postgres` (no Redis — see section 6). *Verify:* `docker compose up -d postgres` → healthy.
2. **Schema via plain SQL** — write `init-db.sql` from the `company_cache`/`api_logs` tables in section 4, mounted into the postgres init dir. *Verify:* `\dt` shows both tables.
3. **Unified Pydantic models** — define the request/response shape from section 5 in `app/models.py`. *Verify:* `python -c "import app.models"` succeeds.
4. **VIES connector, tested standalone** — implement `app/registries/vies.py` using `zeep`, wrapped in `tenacity` retry. Write `tests/test_vies.py` against the official VIES test VAT numbers (no network mocking needed — VIES publishes stable test numbers). *Verify:* `pytest tests/test_vies.py -v` passes.
5. **Companies House connector** — implement `app/registries/companies_house.py`, wrapped in `aiolimiter.AsyncLimiter(600, 300)` + `tenacity`. Mock the HTTP client in `tests/test_companies_house.py`. *Verify:* test asserts the limiter blocks a 601st call within a 5-minute window.
6. **INSEE connector** — implement `app/registries/insee.py`, wrapped in `aiolimiter.AsyncLimiter(30, 60)` + `tenacity`. *Verify:* mocked unit test passes.
7. **API Logging implementation** — wrap all upstream registry calls to log details (success/failure, response time, error message) into the `api_logs` table.
8. **Caching layer** — implement the read path as `SELECT ... FROM company_cache WHERE country_code=%s AND company_identifier=%s AND last_updated > NOW() - INTERVAL '30 days'`; on a cache miss, call the registry connector and `UPSERT` the result. No separate expiry job — staleness is just a `WHERE` clause evaluated at read time. *Verify:* a cached row older than 30 days is treated as a miss and triggers a fresh registry call.
9. **FastAPI batch endpoint** — implement `POST /api/v1/enrich` in `app/main.py`, routing each company to its country connector via the `Country Router` from the architecture diagram, cache-first. *Verify:* the curl example in section 5 returns `"cached": false` on first call and `"cached": true` on the second call for the same identifier.
10. **FastAPI single-company endpoint** — implement `GET /api/v1/enrich/{country}/{identifier}` in `app/main.py` with `force_refresh` logic.

## 11. Testing Strategy
Run in this order:
1. **Unit tests (steps 4-6):** each registry connector tested with mocked HTTP responses (VIES against its own published test VAT numbers; Companies House/INSEE against `pytest`-mocked payloads) — this also keeps CI from hitting live rate limits.
2. **Rate limiter test (step 5-6):** fire concurrent requests at a mocked connector and assert `aiolimiter` throttles them to the configured rate — no Redis involved, so this is a plain in-process async test.
3. **Cache test (step 8):** assert a fresh row is served from Postgres without a registry call, and a row older than 30 days triggers a fresh call.
4. **Integration test (step 9-10):** `POST /api/v1/enrich` and `GET /api/v1/enrich/{country}/{identifier}` against a test Postgres, asserting the response shape from section 5.

## 12. Environment Variables
```env
CH_API_KEY=your_companies_house_key
INSEE_BEARER_TOKEN=your_insee_token
DATABASE_URL=postgresql://postgres:secret@postgres:5432/enricher_db
```

