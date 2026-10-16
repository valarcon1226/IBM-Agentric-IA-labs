# API Quality & Contract Testing Engineering (Project 27)

> **Enterprise API Quality Assurance**: Consumer-Driven Contracts (Pact JS v3), Property-Based OpenAPI Fuzzing (Schemathesis), and Automated Regression Testing (Postman / Newman) with Dockerized Pact Broker and CI/CD Gates.

---

## 1. What Exists Today

This project implements a multi-tier API quality engineering framework verifying microservice contracts, OpenAPI schema conformance, resilience against malformed inputs, and functional REST regressions:

1. **Consumer-Driven Contract Testing (Pact JS v3)**:
   - **Consumer**: Web Chat Widget client (`22-web-chat-widget`).
   - **Provider**: WhatsApp Restaurant Assistant FastAPI (`13-whatsapp-restaurant-assistant`).
   - **Contract Assertions**: Valid chat message exchange (200 OK with replies array), Pydantic input validation (422 Unprocessable Entity), and state-induced sliding-window rate limiting (429 Too Many Requests).
   - **Pact Broker & PostgreSQL**: Auto-deployed on `127.0.0.1:8642` with automated publishing, tag/branch versioning, provider verification result reporting, and `can-i-deploy` deployment evaluation.

2. **Property-Based API Fuzzing & Schema Conformance (Schemathesis v4.31.1)**:
   - Automated property-based negative and edge-case fuzzing against Project 20 (`20-ecommerce-order-automation`) OpenAPI 3.1.0 specification.
   - Enforces `not_a_server_error`, `status_code_conformance`, `content_type_conformance`, and `response_schema_conformance`.
   - Identified and documented 7 authentic schema drift defects and unhandled errors without touching read-only production code.

3. **REST CRUD & SLA Regression Suite (Postman / Newman)**:
   - Full lifecycle test suite for **Swagger Petstore v3** (`127.0.0.1:8643`) across Pet, Store, and User domains.
   - 17 HTTP requests executing 49 assertions covering HTTP status codes, JSON schema models, verified deletions (negative 404 tests), and SLA latency budgets (< 500ms).
   - Automated Newman execution with JUnit XML report generation for CI/CD ingestion.

4. **Honest Defect Discovery**:
   - Discovered 2 authentic defects in Project 13 (Docker container path collision and PostgreSQL `VARCHAR(20)` overflow) and 7 schema discrepancies in Project 20, recorded in `docs/BUG-REPORTS.md`.

---

## 2. Test Coverage & Execution Summary

| Quality Pillar                | Designed Scenarios | Automated Scenarios | Deferred | Pass Rate                          | Tooling                        |
| ----------------------------- | ------------------ | ------------------- | -------- | ---------------------------------- | ------------------------------ |
| **Consumer Contracts (Pact)** | 5                  | 5                   | 0        | 100% (3/3 consumer, 3/3 provider)  | `@pact-foundation/pact` 13.2.0 |
| **API Schema Fuzzing**        | 7                  | 7                   | 0        | 100% explored (7 real bugs logged) | `schemathesis` 4.31.1          |
| **Petstore CRUD Regression**  | 17                 | 17                  | 0        | 100% (49/49 assertions passed)     | `newman` 6.2.3                 |
| **Security & Auth Gates**     | 3                  | 3                   | 0        | 100% passed                        | Pact / Schemathesis            |
| **Negative & Edge Cases**     | 2                  | 2                   | 0        | 100% passed                        | Pact / Schemathesis            |
| **Idempotency Verification**  | 1                  | 0                   | 1        | Deferred to phase B                | Database Hook                  |
| **Total**                     | **35**             | **34**              | **1**    | **97.1% Automated**                | —                              |

---

## 3. Architecture & Contract Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        QUALITY ARCHITECTURE                            │
└────────────────────────────────────────────────────────────────────────┘

    [22-web-chat-widget] (Consumer Client)
             │
             │ npm run test:consumer (PactV3 Mock Server)
             ▼
    [pacts/WebChatWidget-RestaurantAssistantAPI.json]
             │
             │ npm run publish:pact
             ▼
    ┌───────────────────────────────────┐
    │  Pact Broker @ 127.0.0.1:8642     │ ◄───────┐
    │  (pactfoundation/pact-broker + DB)│         │
    └─────────────────┬─────────────────┘         │
                      │                           │
                      │ npm run can-i-deploy      │ npm run verify:provider
                      ▼                           │ (publishes results)
              [Deploy Approval]                   │
                                                  │
             ┌────────────────────────────────────┴────────────────┐
             │ 13-whatsapp-restaurant-assistant @ 127.0.0.1:8004  │
             │ (Provider Under Test)                               │
             └─────────────────────────────────────────────────────┘

    [20-ecommerce-order-automation] ◄─── npm run test:schemathesis
    (OpenAPI 3.1.0 @ 127.0.0.1:8000)      (Property-based fuzzing & schema checks)

    [Swagger Petstore v3]           ◄─── npm run test:newman
    (Docker Jetty @ 127.0.0.1:8643)       (17 requests, 49 assertions, JUnit XML)

Legend:
  ─── Fully Implemented & Verified Today
  - - Target / Future Integration (Phase B: Idempotency Queue Hook)
```

---

## 4. Quickstart: How to Run Locally

### Prerequisites

- Node.js 20+ and npm
- Python 3.12+ (via `uv`)
- Docker Desktop

### 1. Setup Dependencies

```powershell
# In 27-api-contract-quality:
npm install
uv venv -p 3.12 .venv
uv pip install -p .venv\Scripts\python.exe -r requirements.txt
```

### 2. Start Test Infrastructure (Pact Broker & Petstore v3)

```powershell
docker compose up -d
```

Ports exposed on loopback:

- Pact Broker: `http://127.0.0.1:8642` (Credentials: `pact_user` / `pact_password`)
- Swagger Petstore: `http://127.0.0.1:8643/api/v3`

### 3. Run Consumer Contract Tests

```powershell
npm run test:consumer
```

Generates the consumer contract in `pacts/WebChatWidget-RestaurantAssistantAPI.json`.

### 4. Publish Contract to Pact Broker

```powershell
npm run publish:pact
```

### 5. Verify Provider Against Live Backend (Project 13)

```powershell
# In a separate terminal or background, start Project 13 with mount overlay:
docker compose -f ..\13-whatsapp-restaurant-assistant\docker-compose.yml -f docker-compose.p13-mount.yml --project-directory ..\13-whatsapp-restaurant-assistant up -d

# Execute provider verification and result publication:
npm run verify:provider
```

### 6. Verify Deployment Gate (`can-i-deploy`)

```powershell
npm run can-i-deploy
```

### 7. Run Schemathesis Property Fuzzing against Project 20

```powershell
# Start Project 20:
docker compose -f ..\20-ecommerce-order-automation\docker-compose.yml up -d

# Execute Schemathesis:
npm run test:schemathesis
```

### 8. Run Postman / Newman Regression Suite

```powershell
npm run test:newman
```

Generates JUnit test report at `reports/newman-junit.xml`.

### 9. Teardown All Environments

```powershell
docker compose down -v
docker compose -f ..\13-whatsapp-restaurant-assistant\docker-compose.yml --project-directory ..\13-whatsapp-restaurant-assistant down -v
docker compose -f ..\20-ecommerce-order-automation\docker-compose.yml down -v
```

---

## 5. Scripts Reference

| Command                     | Action                                                           |
| --------------------------- | ---------------------------------------------------------------- |
| `npm run lint`              | Runs ESLint over TypeScript source and test files                |
| `npm run format:check`      | Verifies code and doc formatting with Prettier                   |
| `npm run test:consumer`     | Executes Jest consumer contract tests with PactV3 mock server    |
| `npm run publish:pact`      | Publishes validated pact to Pact Broker with semantic branch tag |
| `npm run verify:provider`   | Verifies provider API against broker pacts and posts results     |
| `npm run can-i-deploy`      | Queries Pact Broker matrix API to assert deployment safety       |
| `npm run test:newman`       | Runs Postman Petstore v3 suite with CLI and JUnit XML reporter   |
| `npm run test:schemathesis` | Runs property-based schema fuzzing against Project 20 OpenAPI    |

---

## 6. Environment Variables

| Variable               | Description                                     | Default                        |
| ---------------------- | ----------------------------------------------- | ------------------------------ |
| `PACT_BROKER_BASE_URL` | Base URL of Pact Broker                         | `http://127.0.0.1:8642`        |
| `PACT_BROKER_USERNAME` | Basic Auth user for Pact Broker                 | `pact_user`                    |
| `PACT_BROKER_PASSWORD` | Basic Auth password for Pact Broker             | `pact_password`                |
| `PROVIDER_BASE_URL`    | Base URL of Project 13 Restaurant Assistant API | `http://127.0.0.1:8004`        |
| `CONSUMER_VERSION`     | Version string for published consumer contract  | `1.0.0-<git-hash>.<timestamp>` |
| `CONSUMER_BRANCH`      | Git branch tag in Pact Broker                   | `main`                         |

---

## 7. CI/CD Policy

The GitHub Actions workflow `.github/workflows/27-api-contract-quality.yml` enforces two distinct tiers:

- **Fast PR / Push Gate**:
  - Triggers on push touching `27-api-contract-quality/**` and the workflow itself.
  - Runs TypeScript lint, consumer contract generation, spins up Petstore container, and executes Newman regression suite.
- **Workflow Dispatch Gate (Heavy Integration & Fuzzing)**:
  - Spins up Project 13, Project 20, Pact Broker, and Petstore.
  - Performs full consumer publish → provider verification → `can-i-deploy` gate.
  - Executes Schemathesis property fuzzing suite.
  - Validated with `actionlint:1.7.7`.
