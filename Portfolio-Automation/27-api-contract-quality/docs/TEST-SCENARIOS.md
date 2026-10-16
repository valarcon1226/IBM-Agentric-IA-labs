# Test Scenarios — API Quality Catalog (Project 27)

This catalog details 35 test scenarios spanning consumer-driven contracts, OpenAPI schema conformance, property-based fuzzing, REST CRUD lifecycles, authentication, negative paths, and idempotency.

| ID            | Domain      | Scenario Title & Description                                                      | Priority | Decision    | Tags                       | Test Implementation                                   |
| ------------- | ----------- | --------------------------------------------------------------------------------- | -------- | ----------- | -------------------------- | ----------------------------------------------------- |
| **SC-CTR-01** | Contract    | Valid web chat message delivers array of assistant replies (200 OK)               | P1       | Automatizar | `@smoke`, `@contract`      | `tests/consumer/chat-widget.spec.ts`                  |
| **SC-CTR-02** | Contract    | Empty chat message payload returns 422 Unprocessable Entity with error detail     | P1       | Automatizar | `@regression`, `@contract` | `tests/consumer/chat-widget.spec.ts`                  |
| **SC-CTR-03** | Contract    | Excessive chat requests exceeding 30 req/min return 429 Too Many Requests         | P2       | Automatizar | `@regression`, `@contract` | `tests/consumer/chat-widget.spec.ts`                  |
| **SC-CTR-04** | Contract    | Provider verification of contract against live assistant API on port 8004         | P1       | Automatizar | `@smoke`, `@contract`      | `scripts/verify-provider.ts`                          |
| **SC-CTR-05** | Contract    | Can-I-Deploy matrix gate evaluation before allowing production deployment         | P1       | Automatizar | `@smoke`, `@contract`      | `scripts/can-i-deploy.ts`                             |
| **SC-SCH-01** | Schema      | OpenAPI 3.1.0 specification loading and syntactic schema parsing                  | P1       | Automatizar | `@smoke`, `@fuzzing`       | Schemathesis (`http://127.0.0.1:8000/openapi.json`)   |
| **SC-SCH-02** | Schema      | Server resilience check: assert no HTTP 500-599 responses on generated inputs     | P1       | Automatizar | `@regression`, `@fuzzing`  | Schemathesis (`--checks not_a_server_error`)          |
| **SC-SCH-03** | Schema      | Status code conformance: all returned codes must be documented in OpenAPI         | P1       | Automatizar | `@regression`, `@fuzzing`  | Schemathesis (`--checks status_code_conformance`)     |
| **SC-SCH-04** | Schema      | Content-Type conformance: response MIME types must match documented specification | P2       | Automatizar | `@regression`, `@fuzzing`  | Schemathesis (`--checks content_type_conformance`)    |
| **SC-SCH-05** | Schema      | Response body schema conformance: JSON payload conforms to schema models          | P1       | Automatizar | `@regression`, `@fuzzing`  | Schemathesis (`--checks response_schema_conformance`) |
| **SC-SCH-06** | Schema      | URL path and query string resilience against encoded and special characters       | P2       | Automatizar | `@regression`, `@fuzzing`  | Schemathesis property engine                          |
| **SC-SCH-07** | Schema      | Null byte header rejection and input sanitization check                           | P2       | Automatizar | `@security`, `@fuzzing`    | Schemathesis security probe                           |
| **SC-PET-01** | Petstore    | Create new pet record with category, tags, and available status (200 OK)          | P1       | Automatizar | `@smoke`, `@regression`    | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-PET-02** | Petstore    | Fetch pet record by ID and validate returned attributes match created record      | P1       | Automatizar | `@smoke`, `@regression`    | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-PET-03** | Petstore    | Update existing pet record with modified name and sold status (200 OK)            | P2       | Automatizar | `@regression`              | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-PET-04** | Petstore    | Delete pet record by ID and verify confirmation text in response                  | P1       | Automatizar | `@smoke`, `@regression`    | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-PET-05** | Petstore    | Negative: Query previously deleted pet identifier returns 404 Not Found           | P2       | Automatizar | `@regression`, `@negative` | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-STO-01** | Store       | Query store inventory map and assert integer counts for all order statuses        | P1       | Automatizar | `@smoke`, `@regression`    | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-STO-02** | Store       | Place purchase order with quantity, ship date, and placed status (200 OK)         | P1       | Automatizar | `@smoke`, `@regression`    | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-STO-03** | Store       | Retrieve purchase order by order ID and validate completeness flag                | P2       | Automatizar | `@regression`              | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-STO-04** | Store       | Cancel and remove purchase order by ID from order tracking registry               | P2       | Automatizar | `@regression`              | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-STO-05** | Store       | Negative: Query nonexistent purchase order ID returns 404 Not Found               | P2       | Automatizar | `@regression`, `@negative` | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-01** | User        | Register user profile with username, credentials, and contact info                | P1       | Automatizar | `@smoke`, `@regression`    | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-02** | User        | Authenticate user credentials via GET /user/login and capture session token       | P1       | Automatizar | `@smoke`, `@security`      | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-03** | User        | Retrieve registered user profile by username and verify profile details           | P2       | Automatizar | `@regression`              | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-04** | User        | Update user profile with modified email, phone number, and user status            | P2       | Automatizar | `@regression`              | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-05** | User        | Terminate active user authentication session via GET /user/logout                 | P2       | Automatizar | `@regression`, `@security` | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-06** | User        | Delete user account from system via DELETE /user/{username}                       | P2       | Automatizar | `@regression`              | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-USR-07** | User        | Negative: Query deleted user account returns 404 Not Found                        | P2       | Automatizar | `@regression`, `@negative` | Newman (`postman/petstore-v3.collection.json`)        |
| **SC-SEC-01** | Auth        | Reject unauthenticated access to admin order export without session cookie        | P1       | Automatizar | `@security`, `@regression` | Schemathesis (`GET /admin/orders/export`)             |
| **SC-SEC-02** | Auth        | Reject webhook deliveries missing HMAC SHA256 cryptographic signature (401)       | P1       | Automatizar | `@security`, `@regression` | Schemathesis (`POST /webhooks/shopify`)               |
| **SC-SEC-03** | Auth        | Enforce HTTP Basic Authentication on Pact Broker diagnostic endpoints (401)       | P1       | Automatizar | `@security`, `@regression` | Pact Broker Suite (`scripts/publish-pact.ts`)         |
| **SC-NEG-01** | Negative    | Malformed JSON syntax in request body returns 422 Unprocessable Entity            | P2       | Automatizar | `@negative`                | Pact Contract & Schemathesis                          |
| **SC-IDM-01** | Idempotency | Duplicate webhook delivery with identical event payload is safely handled         | P2       | Después     | `@idempotency`             | Not Implemented (Documented in Project 20)            |
| **SC-SLA-01** | Latency     | Strict p95 latency enforcement: all Petstore API calls complete in < 500ms        | P1       | Automatizar | `@smoke`, `@performance`   | Newman assertions across 17 requests                  |

---

## Summary of Decisions

- **Total Scenarios Designed**: 35
- **Automated in Project 27**: 34
- **Deferred / Not Implemented**: 1 (`SC-IDM-01`, requires mock webhook emitter with database deduplication inspection)
