# Risk Analysis — API Quality, Contracts & Fuzzing (Project 27)

Evaluation of risks associated with microservice integrations, API contracts, schema drift, and runtime resilience.

## 1. Risk Matrix

| Impact \ Probability  | 1 - Rare | 2 - Unlikely           | 3 - Moderate            | 4 - Likely              | 5 - Almost Certain |
| --------------------- | -------- | ---------------------- | ----------------------- | ----------------------- | ------------------ |
| **5 - Catastrophic**  |          |                        | **RSK-01** (P3, I5: 15) | **RSK-02** (P4, I5: 20) |                    |
| **4 - Major**         |          | **RSK-04** (P2, I4: 8) | **RSK-03** (P3, I4: 12) | **RSK-05** (P4, I4: 16) |                    |
| **3 - Moderate**      |          | **RSK-06** (P2, I3: 6) | **RSK-07** (P3, I3: 9)  |                         |                    |
| **2 - Minor**         |          |                        | **RSK-08** (P3, I2: 6)  |                         |                    |
| **1 - Insignificant** |          |                        |                         |                         |                    |

---

## 2. Identified Risks & Mitigations

### RSK-01: Provider Breaking Changes Breaking Consumer Widget (Score: 15 — High)

- **Probability**: 3 (Moderate) | **Impact**: 5 (Catastrophic)
- **Description**: Provider API modifies response keys (e.g., renaming `replies` to `messages` or changing string array to object array), causing silent frontend rendering failures in the web widget.
- **Mitigation**: Consumer-Driven Contract testing with Pact JS. Consumer pact published to central Pact Broker; CI runs `can-i-deploy` gate before deploying either service.

### RSK-02: Hidden 500 Errors Triggered by Edge-Case Payloads (Score: 20 — Critical)

- **Probability**: 4 (Likely) | **Impact**: 5 (Catastrophic)
- **Description**: Unhandled exceptions during unexpected payload shapes (e.g. database column truncation on long session IDs, null byte headers, unicode encodings), leading to denial of service or data loss.
- **Mitigation**: Property-based API fuzzing using Schemathesis against OpenAPI schemas with `--checks not_a_server_error`.

### RSK-03: Schema Drift Between Documentation and Runtime Implementation (Score: 12 — High)

- **Probability**: 3 (Moderate) | **Impact**: 4 (Major)
- **Description**: API routes return undocumented status codes (e.g., 401/400 without schema definition) or wrong MIME types (e.g. HTML responses where JSON is documented), breaking automated SDKs and client integrations.
- **Mitigation**: Schemathesis contract conformance checks (`status_code_conformance`, `content_type_conformance`, `response_schema_conformance`).

### RSK-04: Unbounded Rate-Limiting Abuse in Public Chat Endpoints (Score: 8 — Medium)

- **Probability**: 2 (Unlikely) | **Impact**: 4 (Major)
- **Description**: Malicious or misconfigured clients flood `/web/chat`, exhausting backend LLM quotas or database connection pools.
- **Mitigation**: Strict per-session sliding-window rate limiting (30 req/min) contractually asserted in Pact interaction suite with HTTP 429 response verification.

### RSK-05: Regressions in REST CRUD Operations Across Lifecycles (Score: 16 — Critical)

- **Probability**: 4 (Likely) | **Impact**: 4 (Major)
- **Description**: Regressions in resource creation, retrieval, updates, or cascading deletions in core business entities (Pets, Orders, Users).
- **Mitigation**: Automated Postman/Newman end-to-end regression test suite verifying status codes, JSON schema models, and negative 404 lookups.

### RSK-06: SLA Degradation / Latency Spikes Exceeding User Tolerance (Score: 6 — Medium)

- **Probability**: 2 (Unlikely) | **Impact**: 3 (Moderate)
- **Description**: API latency creeps over 500ms under routine operation, degrading customer conversion and checkout flow.
- **Mitigation**: Strict response time assertions (`pm.expect(pm.response.responseTime).to.be.below(500)`) embedded across all Newman test runs.

### RSK-07: Inconsistent Webhook Signature Verification Leading to Unauthorized Mutations (Score: 9 — High)

- **Probability**: 3 (Moderate) | **Impact**: 3 (Moderate)
- **Description**: Webhook endpoints fail to consistently enforce HMAC signatures across payment providers (Shopify, Stripe, WooCommerce).
- **Mitigation**: Negative contract assertions checking 400/401 responses when signature headers are omitted or tampered.

### RSK-08: Container Deployment Port Collisions in CI / Homelab Environments (Score: 6 — Low)

- **Probability**: 3 (Moderate) | **Impact**: 2 (Minor)
- **Description**: Simultaneous test executions collide on default ports (8000, 8080, 5432).
- **Mitigation**: Assigned explicit non-standard loopback bindings (`127.0.0.1:8642` for Pact Broker, `127.0.0.1:8643` for Petstore, `127.0.0.1:8004` for Restaurant API).
