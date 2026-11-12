# API Analysis — ParaBank REST Services

> **Base Endpoint:** `/parabank/services/bank`  
> **OpenAPI Spec:** Available at `/parabank/services/bank/openapi.yaml`  
> **Protocol:** HTTP/1.1 REST (JSON & XML supported via `Accept` header)  
> **Investigation Date:** 2026-10-15

---

## 1. Overview of Architecture

ParaBank exposes its backend banking core via multiple interfaces:

1. **Direct Spring MVC Web Controllers** (`/parabank/*.htm`) handling session-based form submissions and rendering JSP views.
2. **REST API (`/parabank/services/bank/*`)** implemented via Apache CXF / JAX-RS, mapped to the underlying Spring banking beans.
3. **SOAP Services** exposed via `/parabank/services/ParaBank?wsdl` and `/parabank/services/LoanProcessor?wsdl`.

For automated quality engineering, the **REST API** provides high-speed, headless test setup, verification, and deterministic database state resets.

---

## 2. Endpoint Specifications & Observed Behavior

### 2.1 Database Lifecycle & Teardown

- `POST /initializeDB`

  - **Status Code:** `204 No Content`
  - **Payload:** None
  - **Observed Behavior:** Creates HSQLDB tables (Account, Customer, Position, Transaction, Parameter), populates default test customer `john` (ID `12212`) and default accounts (e.g., `12345`, `12456`, `54321`). Resets all configuration parameters to baseline defaults.
  - **Suitability for QA:** Essential for global test suite setup and recovery from corrupt database states.

- `POST /cleanDB`
  - **Status Code:** `204 No Content`
  - **Payload:** None
  - **Observed Behavior:** Retains core seed tables and default customer `john`, but wipes dynamically created customer accounts, transactions, and transient state.
  - **Suitability for QA:** Used in `afterEach` test fixtures to ensure complete database isolation and cleanup verification.

### 2.2 Customer & Authentication

- `GET /login/{username}/{password}`

  - **Status Codes:** `200 OK` (success), `400 Bad Request` (failure)
  - **Headers:** `Accept: application/json`
  - **Success Response Schema:**
    ```json
    {
      "id": 12212,
      "firstName": "John",
      "lastName": "Smith",
      "address": {
        "street": "1431 Main St",
        "city": "Beverly Hills",
        "state": "CA",
        "zipCode": "90210"
      },
      "phoneNumber": "310-447-4121",
      "ssn": "622-11-9999"
    }
    ```
  - **Failure Response Body:** Plain text `Invalid username and/or password`.
  - **Observed Quirk:** REST login is stateless; it does not issue or require a `JSESSIONID` cookie.

- `GET /customers/{customerId}`

  - **Status Code:** `200 OK`
  - **Response Schema:** Returns `Customer` entity matching the ID.

- `POST /customers/update/{customerId}`
  - **Status Code:** `200 OK`
  - **Parameters:** Passed as query parameters (`firstName`, `lastName`, `street`, `city`, `state`, `zipCode`, `phoneNumber`, `ssn`, `username`, `password`).
  - **Response:** String acknowledgment (`Successfully updated customer profile`).

### 2.3 Account Operations

- `GET /customers/{customerId}/accounts`

  - **Status Code:** `200 OK`
  - **Response Schema:** Array of `Account` objects:
    ```json
    [
      {
        "id": 12345,
        "customerId": 12212,
        "type": "CHECKING",
        "balance": -2300.0
      }
    ]
    ```

- `GET /accounts/{accountId}`

  - **Status Code:** `200 OK`
  - **Response Schema:** Single `Account` object with `id`, `customerId`, `type` (`CHECKING` | `SAVINGS` | `LOAN`), and `balance` (number).

- `POST /createAccount`
  - **Status Code:** `200 OK`
  - **Parameters (Query):**
    - `customerId` (int32)
    - `newAccountType` (int32: 0 for CHECKING, 1 for SAVINGS)
    - `fromAccountId` (int32)
  - **Response Schema:** Newly generated `Account` object.

### 2.4 Financial Transactions

- `POST /transfer`

  - **Status Code:** `200 OK`
  - **Parameters (Query):** `fromAccountId`, `toAccountId`, `amount`
  - **Response:** Plain text confirmation string (e.g., `Successfully transferred $100.00 from account #12345 to account #54321`).
  - **Observed Behavior:** Immediately adjusts balances in both accounts and records corresponding `Debit` and `Credit` transactions.

- `POST /deposit`

  - **Status Code:** `200 OK`
  - **Parameters (Query):** `accountId`, `amount`
  - **Response:** Plain text confirmation string.

- `POST /withdraw`

  - **Status Code:** `200 OK`
  - **Parameters (Query):** `accountId`, `amount`
  - **Response:** Plain text confirmation string.

- `POST /billpay`

  - **Status Code:** `200 OK`
  - **Parameters (Query):** `accountId`, `amount`
  - **Body (JSON):** `Payee` object (`name`, `address`, `phoneNumber`, `accountNumber`).
  - **Response Schema:** `BillPayResult` object containing `payeeName`, `amount`, and `accountId`.

- `POST /requestLoan`
  - **Status Code:** `200 OK`
  - **Parameters (Query):** `customerId`, `amount`, `downPayment`, `fromAccountId`
  - **Response Schema:**
    ```json
    {
      "responseDate": "2026-10-16T03:41:40.000Z",
      "loanProviderName": "ParaBank",
      "approved": true,
      "message": null,
      "accountId": 13456
    }
    ```

### 2.5 Transaction Queries

- `GET /accounts/{accountId}/transactions`

  - **Status Code:** `200 OK`
  - **Response Schema:** Array of `Transaction` items:
    ```json
    [
      {
        "id": 12145,
        "accountId": 12345,
        "type": "Credit",
        "date": 1765411200000,
        "amount": 300.0,
        "description": "Check # 1111"
      }
    ]
    ```

- `GET /transactions/{transactionId}`
  - **Status Code:** `200 OK`
  - **Response Schema:** Single `Transaction` object.

---

## 3. Comparative Matrix: Observed Reality vs. Theoretical Specs

| Aspect                 | Theoretical Documentation      | Observed Reality (Empirical)                                                                          | Impact on Automation Strategy                                                       |
| ---------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **DB State on Launch** | "Container ready to use"       | HSQLDB empty; table `Parameter` missing until `/initializeDB` called.                                 | Healthcheck must execute `/initializeDB` to guarantee test readiness.               |
| **Registration API**   | Implied via customer endpoints | REST API lacks registration endpoint; registration requires `register.htm` with session.              | Disposable user fixtures create customer via UI form or seed user `john`.           |
| **Parameter Passing**  | Standard REST bodies (JSON)    | Most state-modifying POST endpoints (`/transfer`, `/createAccount`) take query params, not JSON body. | API Client must pass parameters in query string for CXF endpoints.                  |
| **Response Typing**    | Strict JSON                    | Some endpoints return plain text messages (`Successfully transferred...`) rather than JSON.           | Custom typed wrapper in Playwright parses responses based on endpoint content-type. |
| **Teardown Speed**     | Heavy restart required         | `/cleanDB` executes in < 50ms without restarting container.                                           | Clean teardown can execute in `afterEach` without slowing down the test run.        |
