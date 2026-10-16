# Functional Inventory — ParaBank

> **Version:** ParaBank 24.04 (parasoft/parabank:baseline)  
> **Environment:** Docker container on `127.0.0.1:8640` (Tomcat 11 / Java 25 / HSQLDB 2.7.4)  
> **Documentation Methodology:** All items are strictly segregated into **Observed (Verified via live HTTP/Browser inspection)** vs **Assumed (Inferred from specs/documentation)**.

---

## 1. Web UI Features (`/parabank/*`)

### 1.1 Customer Authentication & Registration

- **Customer Registration (`/parabank/register.htm`)**
  - _Observed:_ Requires an initial `GET /parabank/register.htm` to seed the Spring session attribute `customerForm`. Submitting via POST without an existing session results in HTTP 500 (`IllegalStateException: Expected session attribute 'customerForm'`).
  - _Observed:_ Mandatory form fields: First Name (`customer.firstName`), Last Name (`customer.lastName`), Address (`customer.address.street`), City (`customer.address.city`), State (`customer.address.state`), Zip Code (`customer.address.zipCode`), Phone (`customer.phoneNumber`), SSN (`customer.ssn`), Username (`customer.username`), Password (`customer.password`), Confirm Password (`repeatedPassword`).
  - _Observed:_ On successful registration, displays "Welcome <username> - Your account was created successfully. You are now logged in." A default checking account is automatically created with initial balance ($515.50 by default).
  - _Observed:_ Attempting to register an already existing username shows an error message "This username already exists."
- **Customer Login (`/parabank/login.htm`)**
  - _Observed:_ Left sidebar login form accepts `username` and `password`. Successful authentication redirects to `/parabank/overview.htm` with active session.
  - _Observed:_ Default seed user is `john` / `demo`.
  - _Observed:_ Invalid credentials display error: "The username and password could not be verified."
- **Forgot Login Info (`/parabank/lookup.htm`)**
  - _Observed:_ Lookup form accepts First Name, Last Name, Street, City, State, Zip, and SSN to recover username/password.
- **Customer Logout (`/parabank/logout.htm`)**
  - _Observed:_ Terminates session, removes authentication cookies, and returns to public login panel.

### 1.2 Account Management & Services

- **Accounts Overview (`/parabank/overview.htm`)**
  - _Observed:_ Displays table listing all customer accounts (Account Number, Balance, Available Amount), followed by Total balance calculation.
  - _Observed:_ Clicking any Account Number navigates to Account Details (`/parabank/activity.htm?id=<accountId>`).
- **Open New Account (`/parabank/openaccount.htm`)**
  - _Observed:_ Form allows selecting account type (`CHECKING` or `SAVINGS`) and selecting an existing account from which to transfer initial deposit.
  - _Observed:_ On submit, makes asynchronous POST request to `/parabank/services_proxy/bank/createAccount` and renders confirmation: "Congratulations, your account is now open. Your new account number: <id>".
- **Account Details & Activity (`/parabank/activity.htm`)**
  - _Observed:_ Shows Account Details (Type, Balance, Available) and Account Activity filter form (Activity Period, Type: All/Credit/Debit).
  - _Observed:_ Displays table of transactions with columns: Date, Transaction, Debit (-), Credit (+). Clicking transaction description opens Transaction Details (`/parabank/transaction.htm?id=<id>`).

### 1.3 Financial Operations

- **Transfer Funds (`/parabank/transfer.htm`)**
  - _Observed:_ Accepts Amount, From Account dropdown, To Account dropdown.
  - _Observed:_ Submitting performs fund transfer and displays: "Transfer Complete! $<amount> has been transferred from account #<from> to account #<to>."
  - _Observed:_ Transfer updates balances immediately across both accounts.
- **Bill Pay (`/parabank/billpay.htm`)**
  - _Observed:_ Form accepts Payee Name, Address, City, State, Zip, Phone, Account #, Verify Account #, Amount, and From Account.
  - _Observed:_ On success, displays: "Bill Payment Complete. Bill Payment to <payee> in the amount of $<amount> from account <from> was successful."
- **Request Loan (`/parabank/requestloan.htm`)**
  - _Observed:_ Accepts Loan Amount, Down Payment, and From Account.
  - _Observed:_ Submitting returns Loan Request Processed status: Loan Provider (e.g., ParaBank), Status (`Approved` or `Denied`), and if approved, new loan account number.
- **Find Transactions (`/parabank/findtrans.htm`)**
  - _Observed:_ Provides 4 search criteria for an account: Find by Transaction ID, Find by Date (`MM-DD-YYYY`), Find by Date Range, Find by Amount.
  - _Observed:_ Renders matching transactions in results table.
- **Update Contact Info (`/parabank/updateprofile.htm`)**
  - _Observed:_ Pre-populates customer first name, last name, address, phone. Submitting POST updates profile and displays "Profile Updated".

### 1.4 Administration & Database Controls (`/parabank/admin.htm`)

- **Database Initialization & Cleanup**
  - _Observed:_ Contains Database controls: "Initialize" (calls `action=INIT` on `/parabank/db.htm`) and "Clean" (`action=CLEAN`).
  - _Observed:_ Initialize triggers HSQL schema creation and default mock seed generation.
  - _Observed:_ Clean wipes runtime-created data while leaving base schema intact.
- **JMS Service**
  - _Observed:_ Displays JMS Service Status (Running/Stopped) and toggle button (`/parabank/jms.htm`).
- **Data Access Mode**
  - _Observed:_ Radio options: SOAP, REST (XML), REST (JSON), JDBC* (*default).
- **Application Settings**
  - _Observed:_ Configurable parameters: Initial Balance ($515.50), Minimum Balance ($100.00), Loan Provider (JMS, Web Service, Local), Loan Processor (Available Funds, Down Payment, Combined), Threshold (20%).

---

## 2. REST API Inventory (`/parabank/services/bank/*`)

| Endpoint                                             | HTTP Method | Observed Status          | Content-Type | Description                                                                                   |
| ---------------------------------------------------- | ----------- | ------------------------ | ------------ | --------------------------------------------------------------------------------------------- |
| `/initializeDB`                                      | POST        | 204 No Content           | empty        | Initializes database tables, creates parameters and base seed data.                           |
| `/cleanDB`                                           | POST        | 204 No Content           | empty        | Cleans transient customer accounts and transactions, restoring baseline.                      |
| `/login/{username}/{password}`                       | GET         | 200 OK / 400 Bad Request | JSON / XML   | Returns `Customer` object on success; 400 with "Invalid username and/or password" on failure. |
| `/customers/{customerId}`                            | GET         | 200 OK                   | JSON / XML   | Returns full customer profile for given ID.                                                   |
| `/customers/{customerId}/accounts`                   | GET         | 200 OK                   | JSON / XML   | Returns array of `Account` objects owned by the customer.                                     |
| `/accounts/{accountId}`                              | GET         | 200 OK                   | JSON / XML   | Returns account object with type and balance.                                                 |
| `/createAccount`                                     | POST        | 200 OK                   | JSON / XML   | Query params: `customerId`, `newAccountType`, `fromAccountId`. Returns created `Account`.     |
| `/transfer`                                          | POST        | 200 OK                   | text/plain   | Query params: `fromAccountId`, `toAccountId`, `amount`. Transfers funds.                      |
| `/deposit`                                           | POST        | 200 OK                   | text/plain   | Query params: `accountId`, `amount`. Deposits funds.                                          |
| `/withdraw`                                          | POST        | 200 OK                   | text/plain   | Query params: `accountId`, `amount`. Withdraws funds.                                         |
| `/billpay`                                           | POST        | 200 OK                   | JSON / XML   | Query params: `accountId`, `amount`. Body: `Payee` object. Dispatches bill payment.           |
| `/requestLoan`                                       | POST        | 200 OK                   | JSON / XML   | Query params: `customerId`, `amount`, `downPayment`, `fromAccountId`. Returns `LoanResponse`. |
| `/accounts/{accountId}/transactions`                 | GET         | 200 OK                   | JSON / XML   | Returns list of `Transaction` objects for given account.                                      |
| `/transactions/{transactionId}`                      | GET         | 200 OK                   | JSON / XML   | Returns single `Transaction` details.                                                         |
| `/accounts/{accountId}/transactions/amount/{amount}` | GET         | 200 OK                   | JSON / XML   | Queries transactions by exact amount.                                                         |
| `/accounts/{accountId}/transactions/onDate/{onDate}` | GET         | 200 OK                   | JSON / XML   | Queries transactions by specific date.                                                        |
| `/customers/update/{customerId}`                     | POST        | 200 OK                   | text/plain   | Query params: profile fields. Updates customer information.                                   |

---

## 3. Segregation: Observed vs. Assumed

### Observed (Direct Empirical Evidence)

1. **HSQLDB Initialization Requirement:** The container starts HSQLDB, but the tables (specifically table `Parameter`) do not exist until `/initializeDB` or the Admin INIT button is executed. Attempting to view `/admin.htm` prior to this produces `BadSqlGrammarException: user lacks privilege or object not found: PARAMETER`.
2. **Session Attribute Dependency on Registration:** Direct POST to `/parabank/register.htm` without an existing session cookie fails with HTTP 500 (`Expected session attribute 'customerForm'`). A preceding GET request is strictly required.
3. **REST Content Negotiation:** Endpoints respect the `Accept: application/json` header, returning clean JSON payloads for integration tests.
4. **CleanDB vs InitializeDB behavior:** `cleanDB` clears dynamic accounts created during tests while retaining seed account `john` (12212).

### Assumed (Pending empirical verification / Edge cases)

1. _Concurrent Session Isolation:_ Assumed that concurrent users with distinct JSESSIONID cookies have isolated in-memory session states without cross-contamination.
2. _JMS Integration:_ Assumed that JMS loan processing mode communicates with internal port 61616; currently tests use Web Service / Local loan provider mode.
3. _Rate Limiting / Throttling:_ Assumed that ParaBank has no native rate limiting or anti-automation CAPTCHA, making it suitable for high-throughput automated suites.
