# Risk Analysis — OWASP Juice Shop Testing Suite

## 1. Methodology & Risk Scoring

Risks are evaluated using a standard Probability (1–5) × Impact (1–5) matrix:

$$\text{Risk Score} = \text{Probability (P)} \times \text{Impact (I)}$$

| Score Range |   Severity Level    | Testing Priority | QA Strategy                                                              |
| :---------: | :-----------------: | :--------------: | :----------------------------------------------------------------------- |
| **16 – 25** | **Critical / High** |   P1 (Blocker)   | Mandatory automated smoke test in CI on every push; regression coverage. |
| **9 – 15**  |     **Medium**      |    P2 (Major)    | Automated regression test; nightly or scheduled pipeline execution.      |
|  **1 – 8**  |       **Low**       |    P3 (Minor)    | Automated or manual exploratory test during release validation.          |

---

## 2. Risk Matrix & Failure Mode Inventory

| Risk ID    | Category          | Failure Mode / Vulnerability                                                                                                           |  P  |  I  | Score  |   Level    | QA Mitigation Strategy                                                                    |
| :--------- | :---------------- | :------------------------------------------------------------------------------------------------------------------------------------- | :-: | :-: | :----: | :--------: | :---------------------------------------------------------------------------------------- |
| **RSK-01** | Security / Auth   | **Bypass of Password Policy via API**: Backend `/api/Users` accepts 1-char passwords, bypassing Angular UI validation.                 |  5  |  4  | **20** |  **High**  | Automate API contract validation (`SC-API-02`) and UI form boundary tests (`SC-AUTH-02`). |
| **RSK-02** | Security / Auth   | **Broken Object Level Authorization (BOLA / IDOR)**: `/rest/basket/:id` allows reading any user's cart without ownership verification. |  5  |  5  | **25** |  **High**  | Document in `BUG-REPORTS.md` (BUG-002); isolate test user sessions via `cy.session`.      |
| **RSK-03** | Security / Data   | **Sensitive Data Leakage in JWT**: Password hash (MD5) leaked inside JWT authentication token claims.                                  |  5  |  4  | **20** |  **High**  | Document in `BUG-REPORTS.md` (BUG-003); assert on token structure in `SC-API-03`.         |
| **RSK-04** | Resilience        | **Unhandled 500 Internal Server Errors**: Unhandled database exceptions leak full stack traces in HTML.                                |  4  |  4  | **16** |  **High**  | Test UI resilience with `cy.intercept` stubbing HTTP 500 (`SC-NET-01`, `SC-NET-03`).      |
| **RSK-05** | E-commerce / Core | **Checkout Pipeline Failure**: Inability to finalize payment or create address breaks revenue generation.                              |  3  |  5  | **15** | **Medium** | End-to-end checkout automation (`SC-CHK-01`) running on every CI push (`@smoke`).         |
| **RSK-06** | E-commerce / Cart | **Cart State Synchronization Bug**: Basket items fail to increment or mismatch between `sessionStorage` and backend.                   |  4  |  4  | **16** |  **High**  | Automate basket addition (`SC-CART-01`) and basket verification (`SC-CART-02`).           |
| **RSK-07** | Network           | **Network Latency / Slow Responses**: UI hangs indefinitely or freezes when backend queries take > 1000ms.                             |  4  |  3  | **12** | **Medium** | Network delay simulation with `cy.intercept` (`SC-NET-02`).                               |
| **RSK-08** | UX / Forms        | **Feedback Form Submission Without Validation**: Submitting invalid math captchas or empty comments.                                   |  4  |  3  | **12** | **Medium** | Automate feedback form validation (`SC-FDBK-01`, `SC-FDBK-02`).                           |
| **RSK-09** | Localization      | **Missing Translation Bundles (i18n)**: Switching languages renders raw translation keys or broken templates.                          |  3  |  2  | **6**  |  **Low**   | Automate language switch and bundle verification (`SC-LANG-01`).                          |
| **RSK-10** | Search / Catalog  | **Search Engine Injection / Crash**: Malformed query input crashes catalog or exposes database errors.                                 |  4  |  4  | **16** |  **High**  | Catalog search testing (`SC-CAT-01`, `SC-CAT-02`).                                        |

---

## 3. High-Priority Risk Mitigation Summary

1. **Critical Path Safeguards**: The end-to-end checkout path (`RSK-05`, `RSK-06`) is safeguarded by `@smoke` tests running on Chromium-free Microsoft Edge in CI.
2. **Resilience Testing**: `cy.intercept` injects network latency and HTTP 500 status codes to verify that the application recovers without crashing (`RSK-04`, `RSK-07`).
3. **Session & Data Isolation**: All automated tests run with dynamically seeded disposable users (`RSK-01`, `RSK-02`) so no test relies on pre-existing shared state.
