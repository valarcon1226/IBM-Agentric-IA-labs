# Traceability Matrix — ParaBank QA Framework

> **Mapping:** Risk ID $\rightarrow$ Test Scenario ID $\rightarrow$ Implementation / Test Spec File  
> **Rule:** Non-automated scenarios are marked as `Not Implemented (Manual/Backlog)`.

---

| Risk ID        | Risk Title                                          | Scenario ID | Test Scenario Title                                     | Automated File / Status          |
| -------------- | --------------------------------------------------- | ----------- | ------------------------------------------------------- | -------------------------------- |
| **RSK-FIN-01** | Transfer balances miscalculated / desynchronized    | SCN-TRF-01  | UI: Transfer funds between accounts                     | `tests/ui/transfers.spec.ts`     |
| **RSK-FIN-01** | Transfer balances miscalculated / desynchronized    | SCN-TRF-02  | Hybrid: Transfer via UI and assert balance via REST API | `tests/ui/transfers.spec.ts`     |
| **RSK-FIN-01** | Transfer balances miscalculated / desynchronized    | SCN-API-06  | API: Transfer funds via POST `/transfer`                | `tests/api/transactions.spec.ts` |
| **RSK-FIN-02** | Overdraft / balance boundary handling               | SCN-TRF-04  | Attempt transfer exceeding available balance            | `Not Implemented (Manual)`       |
| **RSK-FIN-02** | Overdraft / balance boundary handling               | SCN-API-05  | API: Deposit funds and verify balance increase          | `tests/api/transactions.spec.ts` |
| **RSK-DAT-01** | Database state leakage between test executions      | SCN-API-09  | API: Execute cleanDB and verify data wiped              | `tests/api/admin.spec.ts`        |
| **RSK-DAT-01** | Database state leakage between test executions      | Fixture     | Disposable customer teardown & cleanup check            | `src/fixtures/testFixture.ts`    |
| **RSK-DAT-02** | Initial database uninitialized on container startup | SCN-API-10  | API: Initialize database restores seed dataset          | `tests/api/admin.spec.ts`        |
| **RSK-DAT-02** | Initial database uninitialized on container startup | Healthcheck | Docker Compose container healthcheck                    | `docker-compose.yml`             |
| **RSK-SEC-01** | Authentication bypass / session fixation            | SCN-LOG-01  | UI: Valid customer authentication                       | `tests/ui/auth.spec.ts`          |
| **RSK-SEC-01** | Authentication bypass / session fixation            | SCN-LOG-02  | UI: Invalid credentials rejection                       | `tests/ui/auth.spec.ts`          |
| **RSK-SEC-01** | Authentication bypass / session fixation            | SCN-LOG-04  | UI: Logout invalidates active session                   | `tests/ui/auth.spec.ts`          |
| **RSK-SEC-01** | Authentication bypass / session fixation            | SCN-API-01  | API: Authenticate user john/demo                        | `tests/api/accounts.spec.ts`     |
| **RSK-SEC-02** | Duplicate customer username collision               | SCN-REG-04  | UI: Register existing username                          | `Not Implemented (Backlog)`      |
| **RSK-REG-01** | Session attribute missing on registration POST      | SCN-REG-01  | UI: Complete valid customer registration                | `tests/ui/auth.spec.ts`          |
| **RSK-REG-01** | Session attribute missing on registration POST      | SCN-REG-02  | UI: Registration with missing mandatory fields          | `tests/ui/auth.spec.ts`          |
| **RSK-REG-01** | Session attribute missing on registration POST      | SCN-REG-05  | API: Direct POST without session                        | `Not Implemented (Manual)`       |
| **RSK-API-01** | REST API contract schema drifting                   | SCN-API-02  | API: Customer accounts schema validation                | `tests/api/accounts.spec.ts`     |
| **RSK-API-01** | REST API contract schema drifting                   | SCN-API-03  | API: Query single account details                       | `tests/api/accounts.spec.ts`     |
| **RSK-API-01** | REST API contract schema drifting                   | SCN-API-04  | API: Create account endpoint validation                 | `tests/api/accounts.spec.ts`     |
| **RSK-API-01** | REST API contract schema drifting                   | SCN-API-07  | API: Account transactions list schema                   | `tests/api/transactions.spec.ts` |
| **RSK-API-01** | REST API contract schema drifting                   | SCN-API-08  | API: Request loan response schema                       | `tests/api/transactions.spec.ts` |
| **RSK-LOA-01** | Loan approval algorithm validation                  | SCN-LOA-01  | UI: Request loan with sufficient down payment           | `tests/ui/loan.spec.ts`          |
| **RSK-LOA-01** | Loan approval algorithm validation                  | SCN-LOA-02  | UI: Request loan with insufficient down payment         | `Not Implemented (Backlog)`      |
| **RSK-BIL-01** | Bill payment deducted without proper validation     | SCN-BIL-01  | UI: Submit valid bill payment                           | `tests/ui/billpay.spec.ts`       |
| **RSK-BIL-01** | Bill payment deducted without proper validation     | SCN-BIL-02  | UI: Verify account balance deducted by bill pay         | `Not Implemented (Backlog)`      |
| **RSK-VIS-01** | Visual regressions on banking interfaces            | SCN-VIS-01  | Visual: Login page screenshot match                     | `tests/visual/login.spec.ts`     |
| —              | Accounts Overview verification                      | SCN-ACC-01  | UI: Verify accounts overview table & total              | `tests/ui/accounts.spec.ts`      |
| —              | Account Activity verification                       | SCN-ACC-02  | UI: View account activity history                       | `tests/ui/accounts.spec.ts`      |
| —              | Account Creation                                    | SCN-OPN-01  | UI: Open new savings account                            | `tests/ui/accounts.spec.ts`      |
| —              | Account Creation                                    | SCN-OPN-02  | UI: Open new checking account                           | `Not Implemented (Backlog)`      |
| —              | Transaction Search                                  | SCN-FND-01  | UI: Find transaction by amount                          | `tests/ui/accounts.spec.ts`      |
| —              | Profile Management                                  | SCN-PRF-01  | UI: Update customer contact details                     | `tests/ui/profile.spec.ts`       |
| —              | Profile Management                                  | SCN-PRF-03  | UI: Verify profile persistence                          | `Not Implemented (Manual)`       |
