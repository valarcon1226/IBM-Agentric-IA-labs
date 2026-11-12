# Risk Analysis — ParaBank Automated QA

> **Scoring Model:** Risk Score = Probability (1–5) × Impact (1–5).  
> **Classification:** High (15–25), Medium (8–14), Low (1–7).

---

## 1. Risk Evaluation Matrix

| Risk ID        | Risk Description                                                                           | Category            | Prob (1–5) | Impact (1–5) | Score (1–25) | Severity | Mitigation Strategy                                                                        | Test Mapping                                              |
| -------------- | ------------------------------------------------------------------------------------------ | ------------------- | :--------: | :----------: | :----------: | :------: | ------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| **RSK-FIN-01** | Transfer balances miscalculated or desynchronized between UI and database.                 | Financial Integrity |     3      |      5       |    **15**    |   High   | Hybrid end-to-end tests: transfer funds in UI and assert balance immediately via REST API. | `tests/ui/transfers.spec.ts`                              |
| **RSK-FIN-02** | Overdraft / negative balance handling without proper warnings or controls.                 | Financial Integrity |     4      |      4       |    **16**    |   High   | Test transfer and withdrawal boundaries on accounts near zero or negative.                 | `tests/api/transactions.spec.ts`                          |
| **RSK-DAT-01** | Database state leakage between test executions polluting assertions.                       | Test Isolation      |     4      |      4       |    **16**    |   High   | Automated `cleanDB` teardown in test fixtures verifying customer removal.                  | `src/fixtures/testFixture.ts`                             |
| **RSK-DAT-02** | Initial database uninitialized on container startup causing 500 errors.                    | Infrastructure      |     5      |      3       |    **15**    |   High   | Docker healthcheck calls `initializeDB` before marking container healthy.                  | `docker-compose.yml`                                      |
| **RSK-SEC-01** | Authentication bypass or session fixation across customer logins.                          | Security            |     2      |      5       |    **10**    |  Medium  | Validate credentials verification and session teardown on logout.                          | `tests/ui/auth.spec.ts`                                   |
| **RSK-SEC-02** | Duplicate customer username registration causing collision.                                | Data Integrity      |     3      |      4       |    **12**    |  Medium  | Test registration with already existing username and assert rejection.                     | `tests/ui/auth.spec.ts`                                   |
| **RSK-REG-01** | Session attribute missing on registration POST causing HTTP 500.                           | Web Flow            |     4      |      3       |    **12**    |  Medium  | Ensure client flows initiate with GET before submitting registration.                      | `tests/ui/auth.spec.ts`                                   |
| **RSK-XBR-01** | Browser engine differences in CSS rendering or form input events (Edge vs WebKit/Firefox). | Cross-Browser       |     3      |      3       |    **9**     |  Medium  | Cross-browser test execution targeting Chromium/Edge, Firefox, and WebKit.                 | `playwright.config.ts`                                    |
| **RSK-API-01** | REST API contract schema drifting or dropping mandatory fields.                            | API Contract        |     2      |      4       |    **8**     |  Medium  | Strictly typed TypeScript interfaces validating JSON response payloads.                    | `tests/api/accounts.spec.ts`                              |
| **RSK-LOA-01** | Loan approval algorithm accepting invalid or insufficient down payments.                   | Business Logic      |     3      |      3       |    **9**     |  Medium  | Test loan requests with varying down payment percentages.                                  | `tests/ui/loan.spec.ts`, `tests/api/transactions.spec.ts` |
| **RSK-BIL-01** | Bill payment deducted without valid account number or payee validation.                    | Financial Integrity |     2      |      4       |    **8**     |  Medium  | Validate bill payment response schema and account balance deduction.                       | `tests/ui/billpay.spec.ts`                                |
| **RSK-VIS-01** | Visual regressions or layout breakage on customer-facing banking screens.                  | UI Quality          |     3      |      2       |    **6**     |   Low    | Playwright visual regression screenshot comparison (`toHaveScreenshot`).                   | `tests/visual/login.spec.ts`                              |

---

## 2. Priority Risk Ranking

1. **RSK-FIN-01 / RSK-FIN-02 (Financial Integrity):** In a banking application, monetary discrepancies are unacceptable. High-priority automated tests verify debit/credit synchronization across UI and REST endpoints.
2. **RSK-DAT-01 / RSK-DAT-02 (Test Reliability & Environment):** Flaky tests commonly stem from unclean state. Automated fixture cleanup and deterministic container healthchecks eliminate non-deterministic test failures.
3. **RSK-SEC-01 / RSK-SEC-02 (Authentication & Registration):** Gateway into user accounts. Covered by `@smoke` tests to fail fast if broken.
