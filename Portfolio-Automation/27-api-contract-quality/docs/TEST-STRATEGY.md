# Test Strategy — API Contract Quality (Project 27)

This document establishes the testing architecture, quality gates, tools, and execution methodology for API quality assurance.

## 1. Testing Pyramid & Pillars

```
             ▲
            / \
           /   \     Postman / Newman: End-to-End Regression & SLA
          /-----\    (17 requests, 49 assertions against Petstore v3)
         /       \
        /---------\  Schemathesis: Property-Based Fuzzing & Schema Conformance
       /           \ (171 test cases against OpenAPI 3.1.0)
      /-------------\
     /               \ Pact: Consumer-Driven Contracts & Can-I-Deploy
    /-----------------\ (Pact JS v3 + Pact Broker + PostgreSQL)
```

### Pillar 1: Consumer-Driven Contract Testing (Pact JS)

- **Role**: Decouples consumer frontend evolution from backend deployment cycles without needing live microservice integration environments.
- **Consumer**: Web Chat Widget (`WebChatWidget`).
- **Provider**: Restaurant Assistant API (`RestaurantAssistantAPI`).
- **Mechanism**:
  1. Consumer test executes locally against a Mock Server (`PactV3`), generating a validated JSON pact contract.
  2. The pact is published to a Dockerized **Pact Broker** (`127.0.0.1:8642`) with semantic versioning and branch tags.
  3. Provider verification executes against the actual provider API running on `127.0.0.1:8004`, testing positive responses, 422 validation, and state-induced 429 rate limiting.
  4. `can-i-deploy` query checks matrix compatibility before deployment approval.

### Pillar 2: Property-Based Schema Fuzzing (Schemathesis)

- **Role**: Discovers unhandled edge cases, 5xx server crashes, undocumented HTTP status codes, and media type violations.
- **Target**: Project 20 E-commerce Order Automation API (`127.0.0.1:8000/openapi.json`).
- **Checks Enforced**:
  - `not_a_server_error`: Asserts that no generated payload causes HTTP 500-599 responses.
  - `status_code_conformance`: Verifies every status code returned is explicitly defined in OpenAPI.
  - `content_type_conformance`: Verifies `Content-Type` matches OpenAPI declaration.
  - `response_schema_conformance`: Validates response body against OpenAPI JSON schema models.

### Pillar 3: Automated REST CRUD & SLA Regression (Postman / Newman)

- **Role**: Full functional regression testing across multiple business domains (Pets, Orders, Users).
- **Target**: Swagger Petstore v3 (`127.0.0.1:8643/api/v3`).
- **Assertions Enforced Per Request**:
  - HTTP Status Code Verification (200, 404).
  - Strict Response Time Latency Budget (< 500ms).
  - JSON Schema Structural Validation (via JSON schema validators).
  - Data Integrity Assertions (matching created vs retrieved properties).
- **Reporting**: Automated execution via Newman with console output and JUnit XML export (`reports/newman-junit.xml`).

---

## 2. Environment & Infrastructure Isolation

- **Dockerized Dependencies**: Fixed version tags only (`pactfoundation/pact-broker:2.107.0.1`, `postgres:15-alpine`, `swaggerapi/petstore3:1.0.19`).
- **Strict Network Port Binding**: All containers bind strictly to `127.0.0.1` on designated ports to avoid interface leakage and collisions:
  - Pact Broker: `127.0.0.1:8642`
  - Swagger Petstore v3: `127.0.0.1:8643`
  - Provider API (Project 13): `127.0.0.1:8004`
  - Fuzzing API (Project 20): `127.0.0.1:8000`
- **Zero Artifact Leaks**: Post-execution cleanup ensures all containers and volumes are dropped (`docker compose down -v`).

---

## 3. CI/CD Pipeline Strategy

- **Push Trigger (Fast Gates)**:
  - Linting: Strict ESLint + Prettier check.
  - Consumer Contract Suite: Jest + Pact JS generating pact artifact.
  - Postman / Newman Regression: Runs against Dockerized Petstore v3 in CI runner.
- **Workflow Dispatch (Full Integration & Fuzzing)**:
  - Spins up Project 13 & Project 20 containers.
  - Publishes pact to Pact Broker.
  - Runs Provider Verification against live Project 13.
  - Runs `can-i-deploy` verification gate.
  - Executes Schemathesis fuzzing against Project 20 OpenAPI.
