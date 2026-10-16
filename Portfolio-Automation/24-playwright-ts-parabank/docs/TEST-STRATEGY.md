# Test Strategy — ParaBank Quality Engineering

> **Target Application:** ParaBank Financial Portal  
> **Framework:** Playwright Test + TypeScript (Strict)  
> **Scope:** UI End-to-End, Headless REST API, Visual Regression, Hybrid UI+API Reconciliation

---

## 1. Objectives & Principles

1. **Deterministic Execution:** No flakiness. Zero arbitrary sleeps (`setTimeout` / `page.waitForTimeout` are forbidden). Tests wait on explicit DOM states, network responses, or API assertions.
2. **Speed & Efficiency:** API tests run headless via CXF endpoints for sub-second verification. UI tests leverage lightweight Page Objects with targeted locators.
3. **Data Independence:** Every test either operates on isolated, dynamically generated customer fixtures or restores baseline state via `/cleanDB`.
4. **Shift-Left Quality Gates:** Strict ESLint, Prettier formatting, and TypeScript compiler checks run prior to test execution.

---

## 2. Test Pyramid & Automation Levels

```
               / \
              /   \      Visual Regression (1)
             / UI  \     UI Functional (11)
            / Hybrid\    UI + API Balance Reconciliation (1)
           /---------\
          /    API    \  REST Contract & Transaction (10)
         /-------------\
```

### 2.1 API Testing (`tests/api/`)

- Interacts directly with `/parabank/services/bank/*` using Playwright's `APIRequestContext`.
- Verifies HTTP status codes, response headers, typed payload structures, and database persistence.
- Fast execution path used in CI PR checks.

### 2.2 UI Testing (`tests/ui/`)

- Page Object Model (POM) pattern encapsulating page interactions and locators.
- Emulates user journeys: registration, login, opening accounts, transferring funds, bill pay, loan requests, transaction search, and updating profile information.
- Uses accessible, resilient locators (`getByRole`, `getByLabel`, `getByText`).

### 2.3 Hybrid UI+API Testing

- Executes an end-user action via UI (e.g., fund transfer).
- Immediately queries the backend REST API (`/parabank/services/bank/accounts/{id}`) to verify that the database reflected the transfer accurately, preventing UI masking of backend bugs.

### 2.4 Visual Regression Testing (`tests/visual/`)

- Uses Playwright's `toHaveScreenshot()` to detect unintended layout shifts, font regressions, or styling anomalies on core screens (e.g., the Login landing page).

---

## 3. Browser Matrix & Channel Policy

Per enterprise QA standards and repository rules:

- **Primary Browser (Local & Push CI):** **Microsoft Edge** (`channel: 'msedge'`). Never Google Chrome.
- **Secondary Browsers (Scheduled & Manual CI):** **Mozilla Firefox** and **WebKit** (Safari engine).
- **Execution Strategy:** Push runs fast smoke + API + Edge. Full cross-browser matrix runs on `workflow_dispatch`.

---

## 4. Test Suite Categorization & Tags

| Tag           | Purpose                                                                       | Execution Trigger     | SLA / Target Time |
| ------------- | ----------------------------------------------------------------------------- | --------------------- | ----------------- |
| `@smoke`      | Critical path smoke tests (Login, Registration, Overview, Transfer, Base API) | Push, PR, Post-deploy | < 30 seconds      |
| `@regression` | Comprehensive functional coverage, negative paths, boundary cases, visual     | Nightly, Dispatch     | < 2 minutes       |

---

## 5. Test Data Lifecycle & Isolation

1. **Transient Users:** Dynamic usernames generated via timestamp/nanoid format (`testuser_<timestamp>`).
2. **Setup:** Registered on demand either through form automation or initial seed dataset (`john` / `demo`).
3. **Teardown & Verification:** In `testFixture.ts`, `afterEach` issues a `POST /cleanDB` and verifies via `GET /login/{username}/{password}` that dynamic credentials no longer authenticate.

---

## 6. Flaky Test Management Policy

- **Retries:** Disabled locally (`retries: 0`) to immediately expose unstable selectors or race conditions during development. Set to `retries: 2` in CI to handle transient network drops.
- **Artifacts:** On failure, Playwright automatically preserves traces (`trace: 'retain-on-failure'`), video recording (`video: 'retain-on-failure'`), and full-page screenshots (`screenshot: 'only-on-failure'`).
- **Tracing:** Any flaky test observed in CI must be reviewed using Playwright Trace Viewer (`npx playwright show-trace`) and reported in `docs/BUG-REPORTS.md`.
