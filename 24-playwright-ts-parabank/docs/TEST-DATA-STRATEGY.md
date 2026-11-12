# Test Data Strategy — ParaBank Quality Engineering

> **Principle:** Disposable, isolated, and synthetic test data with verified teardown.

---

## 1. Principles of Test Data Management

1. **No Real PII (Personally Identifiable Information):** All customer names, addresses, phone numbers, and Social Security Numbers are explicitly synthetic (e.g., `Test User`, `999-99-9999`, `555-0100`).
2. **Dynamic Generation:** Usernames and unique entity values are parameterized using timestamp and random seeds (`user_<timestamp>_<random>`) to avoid collisions during parallel execution.
3. **Controlled Baseline Data:** ParaBank's default seed customer (`john` / `demo`) with ID `12212` is treated as a deterministic read-only baseline for non-destructive smoke tests.
4. **Verified Cleanup (Disposable Customer Fixture):** Any dynamically created state (new customer registrations, transient transfers, new accounts) is cleared using the backend database management endpoints (`/cleanDB`), and the test suite explicitly verifies that dynamic entities no longer exist.

---

## 2. Test Data Categories & Lifecycles

### 2.1 Static Seed Baseline Data (Read-Only)

- **Customer:** `john` / `demo`
- **Customer ID:** `12212`
- **Pre-existing Accounts:**
  - `12345` (CHECKING, initial balance: -$2300.00)
  - `12456` (CHECKING, initial balance: $10.45)
  - `54321` (CHECKING, initial balance: $1351.12)
  - `13344` (SAVINGS, initial balance: $1231.10)
- **Usage:** Read-only queries, transaction history lookups, baseline API schema validation.

### 2.2 Disposable Dynamic Customers (`disposableCustomer` Fixture)

- **Lifecycle:**
  1. **Creation:** Generated per test with synthetic attributes:
     - Username: `testuser_<timestamp>`
     - Password: `Password123!`
     - Name: `Fictitious QAUser`
     - SSN: `000-00-0000`
  2. **Execution:** Customer executes transactional flows (transfers, opening accounts, bill pay).
  3. **Teardown:** `afterEach` hook issues `POST /parabank/services/bank/cleanDB`.
  4. **Verification:** The hook issues a follow-up `GET /parabank/services/bank/login/{username}/{password}` and asserts that the response returns HTTP 400 Bad Request ("Invalid username and/or password"), confirming that dynamic data was purged.

### 2.3 Database Reset Architecture

```
+-----------------------------------------------------------+
|                   Test Execution Cycle                   |
|                                                           |
| 1. Test Setup      --> Creates dynamic customer / accounts |
| 2. Test Action     --> Performs UI / API operations       |
| 3. Assertions      --> Validates UI/API state             |
| 4. Teardown Hook   --> Calls POST /cleanDB                |
| 5. Verification    --> Asserts customer removed (400)     |
+-----------------------------------------------------------+
```
