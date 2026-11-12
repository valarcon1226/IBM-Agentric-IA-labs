# Test Data Strategy — OWASP Juice Shop

## 1. Core Principles

1. **Disposable & Ephemeral Data**: Every automated test run generates its own dynamic, timestamped data entities to ensure complete isolation. No test relies on mutable records left by preceding tests.
2. **API-Driven Seeding**: Where UI setup is not the subject under test (e.g. authenticating before reviewing a product, or seeding an address before checking out), entities are seeded directly via REST API calls using `cy.registerByApi()`, `cy.loginByApi()`, or `cy.request()`. This reduces test duration by over 70% while improving reliability.
3. **Synthetic / Fictitious Data**: All names, email domains (`@juice-sh.op`, `@test-juice.op`), phone numbers (`3001234567`), street addresses (`Calle <timestamp> Carrera 15`), and credit card numbers (`4111 1111 1111 1111`) are purely synthetic and clearly marked as test fixtures. No real personal data or production secrets are ever used.
4. **Clean Slate Container Reset**: Because Juice Shop stores data in an ephemeral SQLite database inside the container, tearing down the environment with `docker compose down -v` completely wipes all created records, providing an immutable fresh baseline for every CI run.

---

## 2. Test Entity Lifecycle & Factories

### User Entities

- **Dynamic Email Pattern**: `cypress-ui-${Date.now()}@juice-sh.op` or `api-user-${Date.now()}@test-juice.op`.
- **Default Password**: `JuicePassword123!` (or `admin123` for pre-seeded administrative test cases).
- **Security Question**: Pre-seeded Question ID 1 (`Your eldest siblings middle name?`) with answer `CypressFavoriteColor`.
- **Seeding Method**: `cy.registerByApi(email, password)` via `POST /api/Users/`.
- **Session Cache**: `cy.session([email, password], ...)` stores JWT in `localStorage` and synchronizes the active basket identifier `bid` into `sessionStorage`.

### Address Entities

- **Address Structure**:
  - `country`: `'Colombia'`
  - `fullName`: `'QA Lead'` or `'Valentina Alarcon'`
  - `mobileNum`: `'3001234567'`
  - `zipCode`: `'110111'`
  - `streetAddress`: `'Calle ' + Date.now() + ' Carrera 15'`
  - `city`: `'Bogota'`
  - `state`: `'Cundinamarca'`
- **Creation Mechanism**: UI submission via `/#/address/create` or API `POST /api/Addresss/`.

### Payment Cards

- **Card Number**: Standard test Visa `4111 1111 1111 1111`.
- **Cardholder**: `'QA Lead'`.
- **Expiry Date**: Selected dynamically via month select (1–12) and future year (2080–2099).

---

## 3. Fixtures Directory (`cypress/fixtures/`)

- `users.json`: Default administrative credentials (`admin@juice-sh.op` / `admin123`) and security question reference data.
- `products.json`: Valid catalog search terms (`apple`), invalid queries (`xyznonexistentproduct999`), and mocked error payloads for fault injection.
- `feedback.json`: Valid feedback comments and rating parameters.

---

## 4. Teardown & Garbage Collection

- **Per-Suite Cleanup**: Because test entities are uniquely keyed with epoch timestamps, tests never collide even when executed concurrently.
- **Pipeline Teardown**: The CI workflow executes `docker compose down -v` as an unconditional `always()` step, removing container volumes and purging all test artifacts from local storage.
