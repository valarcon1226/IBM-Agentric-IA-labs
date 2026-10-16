# Test Scenarios Catalog — ParaBank

> **Total Scenarios Designed:** 49  
> **Status Summary:** Automated: 25 · Manual: 12 · Later / Backlog: 12  
> **Coverage Areas:** Registration, Authentication, Accounts, Transfers, Bill Pay, Loans, Transactions Search, Profile, API, Visual.

---

## 1. Authentication & Registration (REG / LOG)

| Scenario ID    | Title / Description                                                                             | Priority | Decision |      Tag      | Type |
| -------------- | ----------------------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-REG-01** | Register new customer with valid unique data and verify automatic initial account creation      |    P1    | Automate |   `@smoke`    |  UI  |
| **SCN-REG-02** | Attempt registration with missing mandatory fields (first name, password) and verify validation |    P2    | Automate | `@regression` |  UI  |
| **SCN-REG-03** | Attempt registration with mismatching password and repeated password fields                     |    P2    |  Later   | `@regression` |  UI  |
| **SCN-REG-04** | Attempt registration using an already existing username and verify error message                |    P2    |  Later   | `@regression` |  UI  |
| **SCN-REG-05** | Attempt direct POST to registration endpoint without session and handle HTTP 500 gracefully     |    P3    |  Manual  |    manual     | API  |
| **SCN-LOG-01** | Login with valid credentials (`john` / `demo`) and verify redirection to Accounts Overview      |    P1    | Automate |   `@smoke`    |  UI  |
| **SCN-LOG-02** | Login with invalid username/password combination and verify authentication error                |    P2    | Automate | `@regression` |  UI  |
| **SCN-LOG-03** | Login with empty username and password fields                                                   |    P3    |  Later   | `@regression` |  UI  |
| **SCN-LOG-04** | Successful logout terminates active session and redirects to customer login panel               |    P1    | Automate | `@regression` |  UI  |
| **SCN-LOG-05** | Forgot login info lookup retrieves customer credentials by profile data                         |    P3    |  Manual  |    manual     |  UI  |

---

## 2. Accounts & Balance Overview (ACC / OPN)

| Scenario ID    | Title / Description                                                                 | Priority | Decision |      Tag      | Type |
| -------------- | ----------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-ACC-01** | View Accounts Overview table displaying account numbers, balances, and total sum    |    P1    | Automate |   `@smoke`    |  UI  |
| **SCN-ACC-02** | Click account number link and view Account Details and Activity history             |    P2    | Automate | `@regression` |  UI  |
| **SCN-ACC-03** | Filter account activity by period (All vs Current Month) and type (Credit vs Debit) |    P3    |  Manual  |    manual     |  UI  |
| **SCN-ACC-04** | Verify total balance calculation matches sum of individual account balances         |    P2    |  Later   | `@regression` |  UI  |
| **SCN-OPN-01** | Open new SAVINGS account transferring minimum funds from existing account           |    P1    | Automate |   `@smoke`    |  UI  |
| **SCN-OPN-02** | Open new CHECKING account and verify new account ID generated and shown in overview |    P2    |  Later   | `@regression` |  UI  |
| **SCN-OPN-03** | Attempt opening account when source account has insufficient balance                |    P3    |  Manual  |    manual     |  UI  |

---

## 3. Financial Transfers (TRF)

| Scenario ID    | Title / Description                                                                      | Priority | Decision |      Tag      |  Type  |
| -------------- | ---------------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :----: |
| **SCN-TRF-01** | Transfer valid funds between two internal accounts via UI and verify confirmation banner |    P1    | Automate |   `@smoke`    |   UI   |
| **SCN-TRF-02** | Hybrid E2E: Transfer funds in UI, then verify source & destination balances via REST API |    P1    | Automate | `@regression` | Hybrid |
| **SCN-TRF-03** | Attempt transfer with non-numeric amount string and verify UI input validation           |    P2    |  Later   | `@regression` |   UI   |
| **SCN-TRF-04** | Attempt transfer exceeding available balance (overdraft check)                           |    P2    |  Manual  |    manual     |   UI   |
| **SCN-TRF-05** | Transfer funds to same account as source and verify error handling                       |    P3    |  Later   | `@regression` |   UI   |

---

## 4. Bill Pay Services (BIL)

| Scenario ID    | Title / Description                                                          | Priority | Decision |      Tag      | Type |
| -------------- | ---------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-BIL-01** | Submit valid bill payment to utility company and verify payment confirmation |    P1    | Automate | `@regression` |  UI  |
| **SCN-BIL-02** | Verify account balance deducted by bill payment amount                       |    P2    |  Later   | `@regression` |  UI  |
| **SCN-BIL-03** | Submit bill payment with mismatching account numbers in verify field         |    P2    |  Manual  |    manual     |  UI  |
| **SCN-BIL-04** | Submit bill payment with missing payee address or phone number               |    P3    |  Manual  |    manual     |  UI  |

---

## 5. Loan Application (LOA)

| Scenario ID    | Title / Description                                                                          | Priority | Decision |      Tag      | Type |
| -------------- | -------------------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-LOA-01** | Request loan with sufficient down payment (>= 20%) and verify loan approved with new account |    P1    | Automate | `@regression` |  UI  |
| **SCN-LOA-02** | Request loan with insufficient down payment and verify loan application denied               |    P2    |  Later   | `@regression` |  UI  |
| **SCN-LOA-03** | Request loan with invalid non-numeric amount                                                 |    P3    |  Manual  |    manual     |  UI  |
| **SCN-LOA-04** | Verify loan account created appears under Accounts Overview with negative balance            |    P2    |  Manual  |    manual     |  UI  |

---

## 6. Find Transactions (FND)

| Scenario ID    | Title / Description                                                       | Priority | Decision |      Tag      | Type |
| -------------- | ------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-FND-01** | Find transactions for account by exact amount and verify matching records |    P2    | Automate | `@regression` |  UI  |
| **SCN-FND-02** | Find transaction by specific transaction ID and view details              |    P2    |  Later   | `@regression` |  UI  |
| **SCN-FND-03** | Find transactions by valid date (`MM-DD-YYYY`)                            |    P2    |  Manual  |    manual     |  UI  |
| **SCN-FND-04** | Find transactions by date range (`fromDate` to `toDate`)                  |    P3    |  Later   | `@regression` |  UI  |
| **SCN-FND-05** | Search with non-existent amount and verify empty results message          |    P3    |  Manual  |    manual     |  UI  |

---

## 7. Customer Profile (PRF)

| Scenario ID    | Title / Description                                                                 | Priority | Decision |      Tag      | Type |
| -------------- | ----------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-PRF-01** | Update customer contact information (phone and street) and verify "Profile Updated" |    P2    | Automate | `@regression` |  UI  |
| **SCN-PRF-02** | Clear mandatory profile field and verify update validation error                    |    P3    |  Later   | `@regression` |  UI  |
| **SCN-PRF-03** | Verify profile changes persist across subsequent logins                             |    P2    |  Manual  |    manual     |  UI  |

---

## 8. REST API Services (API)

| Scenario ID    | Title / Description                                                                      | Priority | Decision |      Tag      | Type |
| -------------- | ---------------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :--: |
| **SCN-API-01** | REST API: Authenticate user `john` / `demo` and validate returned customer payload       |    P1    | Automate |   `@smoke`    | API  |
| **SCN-API-02** | REST API: Retrieve accounts list for customer and validate schema                        |    P1    | Automate |   `@smoke`    | API  |
| **SCN-API-03** | REST API: Query single account details by account ID                                     |    P2    | Automate | `@regression` | API  |
| **SCN-API-04** | REST API: Create new account via POST `/createAccount` and verify response               |    P2    | Automate | `@regression` | API  |
| **SCN-API-05** | REST API: Deposit funds into account via POST `/deposit` and verify balance              |    P2    | Automate | `@regression` | API  |
| **SCN-API-06** | REST API: Transfer funds between accounts via POST `/transfer`                           |    P1    | Automate | `@regression` | API  |
| **SCN-API-07** | REST API: Retrieve transaction history for account via GET `/accounts/{id}/transactions` |    P2    | Automate | `@regression` | API  |
| **SCN-API-08** | REST API: Submit loan request via POST `/requestLoan` and validate LoanResponse schema   |    P2    | Automate | `@regression` | API  |
| **SCN-API-09** | REST API: Execute `/cleanDB` and verify transient test data is wiped                     |    P1    | Automate | `@regression` | API  |
| **SCN-API-10** | REST API: Execute `/initializeDB` and verify seed customer and parameters restored       |    P1    | Automate | `@regression` | API  |

---

## 9. Visual Regression (VIS)

| Scenario ID    | Title / Description                                                                         | Priority | Decision |      Tag      |  Type  |
| -------------- | ------------------------------------------------------------------------------------------- | :------: | :------: | :-----------: | :----: |
| **SCN-VIS-01** | Compare Login Page layout and styling against baseline visual snapshot (`toHaveScreenshot`) |    P2    | Automate | `@regression` | Visual |
