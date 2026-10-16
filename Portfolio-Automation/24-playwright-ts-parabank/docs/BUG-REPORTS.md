# Bug Reports — ParaBank (Observed Defects)

> **Policy:** Strict empirical defect reporting. Contains only genuine, reproducible bugs observed and verified directly during investigation and test automation against `parasoft/parabank:baseline`.

---

## BUG-01: Unhandled BadSqlGrammarException on Fresh Startup Accessing `/admin.htm`

- **Severity:** High
- **Priority:** P1
- **Component:** Spring MVC AdminController / HSQLDB DAO
- **Environment:** Docker container `parasoft/parabank:baseline` on `127.0.0.1:8640`
- **Steps to Reproduce:**
  1. Start a fresh container: `docker run -d -p 8640:8080 parasoft/parabank:baseline`.
  2. Wait until Tomcat logs report webapp deployed.
  3. Navigate to `http://127.0.0.1:8640/parabank/admin.htm`.
- **Expected Result:**
  Admin page loads with default settings or prompts that the database requires initialization.
- **Actual Result:**
  HTTP 500 Internal Error page rendered. Tomcat server log shows:
  ```
  org.springframework.jdbc.BadSqlGrammarException: StatementCallback; bad SQL grammar [SELECT name, value FROM Parameter]
  Caused by: org.hsqldb.HsqlException: user lacks privilege or object not found: PARAMETER
  ```
- **Evidence:**
  Observed directly during initial container inspection. Mitigated in test framework via healthcheck executing `POST /parabank/services/bank/initializeDB`.

---

## BUG-02: Unhandled `IllegalStateException` on Direct Registration POST (`register.htm`)

- **Severity:** Medium
- **Priority:** P2
- **Component:** Spring MVC CustomerRegistrationController
- **Environment:** `http://127.0.0.1:8640/parabank/register.htm`
- **Steps to Reproduce:**
  1. Submit a direct HTTP POST to `/parabank/register.htm` with valid registration form fields without an existing `JSESSIONID` session cookie.
  ```bash
  curl -i -d "customer.firstName=Test&customer.lastName=User&...&repeatedPassword=pass" http://127.0.0.1:8640/parabank/register.htm
  ```
- **Expected Result:**
  Server returns HTTP 400 Bad Request or renders form with validation errors.
- **Actual Result:**
  Server throws unhandled HTTP 500:
  ```
  jakarta.servlet.ServletException: Request processing failed: java.lang.IllegalStateException: Expected session attribute 'customerForm'
    at org.springframework.web.method.annotation.ModelFactory.initModel(ModelFactory.java:117)
  ```
- **Evidence:**
  Observed during API investigation. Mitigated in UI and fixture automation by ensuring the registration page is first visited via `GET` to establish the Spring session attribute before form submission.

---

## BUG-03: REST API Returns Inconsistent Content-Types on Error (Plain Text instead of JSON)

- **Severity:** Low
- **Priority:** P3
- **Component:** Apache CXF REST Services (`/services/bank/*`)
- **Environment:** `http://127.0.0.1:8640/parabank/services/bank/login/invalid/wrong`
- **Steps to Reproduce:**
  1. Send request with `Accept: application/json`:
  ```bash
  curl -i -H "Accept: application/json" http://127.0.0.1:8640/parabank/services/bank/login/invalid/wrong
  ```
- **Expected Result:**
  Server returns structured JSON error response: `{"error": "Invalid username and/or password", "code": 400}`.
- **Actual Result:**
  Server returns HTTP 400 with `Content-Type: text/plain;charset=UTF-8` and raw string `Invalid username and/or password`.
- **Evidence:**
  Observed during REST endpoint validation. Automated API client includes custom handler for plain text error responses.
