# Traceability Matrix — API Quality & Contracts (Project 27)

Maps identified risks to corresponding test scenarios and concrete automated test implementations.

| Risk ID    | Risk Description                                | Scenario ID   | Scenario Title                                  | Test Implementation File / Tool                       | Status            |
| ---------- | ----------------------------------------------- | ------------- | ----------------------------------------------- | ----------------------------------------------------- | ----------------- |
| **RSK-01** | Provider breaking changes break consumer widget | **SC-CTR-01** | Valid chat message returns replies array        | `tests/consumer/chat-widget.spec.ts`                  | **Automated**     |
| **RSK-01** | Provider breaking changes break consumer widget | **SC-CTR-02** | Empty message payload returns 422               | `tests/consumer/chat-widget.spec.ts`                  | **Automated**     |
| **RSK-01** | Provider breaking changes break consumer widget | **SC-CTR-04** | Provider verification against live API          | `scripts/verify-provider.ts`                          | **Automated**     |
| **RSK-01** | Provider breaking changes break consumer widget | **SC-CTR-05** | Can-I-Deploy matrix gate evaluation             | `scripts/can-i-deploy.ts`                             | **Automated**     |
| **RSK-02** | Hidden 500 errors triggered by edge payloads    | **SC-SCH-01** | OpenAPI 3.1.0 specification loading             | Schemathesis CLI                                      | **Automated**     |
| **RSK-02** | Hidden 500 errors triggered by edge payloads    | **SC-SCH-02** | Server error fuzzer: no 5xx on edge inputs      | Schemathesis (`--checks not_a_server_error`)          | **Automated**     |
| **RSK-02** | Hidden 500 errors triggered by edge payloads    | **SC-SCH-06** | URL path & query string special char resilience | Schemathesis property engine                          | **Automated**     |
| **RSK-02** | Hidden 500 errors triggered by edge payloads    | **SC-SCH-07** | Null byte header rejection probe                | Schemathesis security probe                           | **Automated**     |
| **RSK-03** | Schema drift between docs and runtime           | **SC-SCH-03** | Status code conformance check                   | Schemathesis (`--checks status_code_conformance`)     | **Automated**     |
| **RSK-03** | Schema drift between docs and runtime           | **SC-SCH-04** | Content-Type MIME conformance check             | Schemathesis (`--checks content_type_conformance`)    | **Automated**     |
| **RSK-03** | Schema drift between docs and runtime           | **SC-SCH-05** | Response body JSON schema conformance           | Schemathesis (`--checks response_schema_conformance`) | **Automated**     |
| **RSK-04** | Unbounded rate-limiting abuse in chat           | **SC-CTR-03** | Rate limit 429 Too Many Requests response       | `tests/consumer/chat-widget.spec.ts`                  | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-PET-01** | Add new pet to store catalog (POST)             | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-PET-02** | Fetch pet details by valid ID (GET)             | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-PET-03** | Update existing pet attributes (PUT)            | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-PET-04** | Delete pet record from catalog (DELETE)         | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-PET-05** | Negative: Query deleted pet returns 404         | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-STO-01** | Query store inventory map (GET)                 | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-STO-02** | Place purchase order for pet (POST)             | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-STO-03** | Retrieve purchase order by ID (GET)             | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-STO-04** | Cancel and remove purchase order (DELETE)       | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-STO-05** | Negative: Nonexistent order ID returns 404      | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-01** | Register user profile with info (POST)          | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-02** | Authenticate credentials (GET login)            | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-03** | Retrieve user profile by username (GET)         | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-04** | Modify user profile details (PUT)               | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-05** | Terminate active user session (GET logout)      | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-06** | Remove user account from system (DELETE)        | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-05** | Regressions in core REST CRUD entities          | **SC-USR-07** | Negative: Query deleted user returns 404        | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-06** | SLA degradation & latency spikes                | **SC-SLA-01** | All Petstore API calls complete in <500ms       | `postman/petstore-v3.collection.json`                 | **Automated**     |
| **RSK-07** | Inconsistent webhook signature verification     | **SC-SEC-01** | Reject unauthenticated access to admin          | Schemathesis (`GET /admin/orders/export`)             | **Automated**     |
| **RSK-07** | Inconsistent webhook signature verification     | **SC-SEC-02** | Reject webhooks without HMAC signature          | Schemathesis (`POST /webhooks/shopify`)               | **Automated**     |
| **RSK-07** | Inconsistent webhook signature verification     | **SC-SEC-03** | Enforce Basic Auth on Pact Broker               | `scripts/publish-pact.ts`                             | **Automated**     |
| **RSK-02** | Hidden 500 errors triggered by edge payloads    | **SC-NEG-01** | Malformed JSON body returns 422                 | Pact Contract & Schemathesis                          | **Automated**     |
| **RSK-07** | Inconsistent webhook signature verification     | **SC-IDM-01** | Webhook delivery deduplication check            | Database inspection script                            | _Not Implemented_ |
