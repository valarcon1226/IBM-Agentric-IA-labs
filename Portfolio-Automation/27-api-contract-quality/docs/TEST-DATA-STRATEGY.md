# Test Data Strategy — API Quality (Project 27)

This document establishes the test data management policies, isolation mechanisms, synthetic generation rules, and cleanup protocols.

## 1. Core Principles

1. **API-Driven Lifecycle (Create → Assert → Delete → Verify 404)**:
   - In Newman / Postman tests, entities (`Pet`, `Order`, `User`) are created dynamically via POST API calls.
   - Assertions run on the created entities.
   - Deletion is executed via DELETE API calls.
   - A final negative GET verifies the entity is gone (HTTP 404), ensuring verified teardown.

2. **100% Synthetic & Non-PII**:
   - All email addresses use the RFC 2606 reserved `.example.com` domain (e.g., `alex.quality@example.com`).
   - Phone numbers use the standard fictional prefix `+1-555-...`.
   - Passwords and usernames are tagged as synthetic (`contract_tester`, `qa_tester`).

3. **Stateless Fuzzing with Property-Based Data**:
   - Schemathesis automatically synthesizes valid, edge-case, and boundary data using Hypothesis strategies derived directly from the OpenAPI 3.1.0 specification.
   - No persistent customer data or real webhooks are consumed.

4. **Ephemeral Docker Volumes & Clean State**:
   - Contract Broker Postgres database uses isolated named volume `27-api-contract-quality_default`.
   - On completion, `docker compose down -v` flushes all persistent state, preventing stale contracts from leaking across test runs.

---

## 2. Test Data Matrix

| Domain             | Entity / Parameter              | Sample Test Value                    | Creation Method         | Cleanup / Verification Method                               |
| ------------------ | ------------------------------- | ------------------------------------ | ----------------------- | ----------------------------------------------------------- |
| **Contract (P13)** | `session_id` (Valid)            | `test-session-123`                   | Sent in POST body       | Volatile Redis/In-memory sliding window (expires in 60s)    |
| **Contract (P13)** | `session_id` (Rate Limit)       | `flood_999`                          | 31 rapid POSTs          | Memory window resets after 60s                              |
| **Petstore**       | `Pet`                           | ID: `8801`, Name: `Golden Retriever` | `POST /pet`             | `DELETE /pet/8801` + `GET /pet/8801` -> 404                 |
| **Petstore**       | `Order`                         | ID: `7701`, Quantity: `3`            | `POST /store/order`     | `DELETE /store/order/7701` + `GET /store/order/7701` -> 404 |
| **Petstore**       | `User`                          | Username: `contract_tester`          | `POST /user`            | `DELETE /user/contract_tester` + `GET /user/...` -> 404     |
| **Fuzzing (P20)**  | Arbitrary Schemathesis payloads | Hypothesis generated                 | Ephemeral HTTP requests | Dropped on container teardown                               |
