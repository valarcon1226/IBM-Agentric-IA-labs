# Test Scenarios Catalog — OWASP Juice Shop

This catalog contains **36 test scenarios** covering functional, security boundary, network resilience, and API requirements across all application domains.

---

## Summary Matrix

| Module                                   | Total Designed | Automated (Phase 26-A) | Manual / Next Phase |
| :--------------------------------------- | :------------: | :--------------------: | :-----------------: |
| **Authentication & Registration**        |       8        |           5            |          3          |
| **Catalog & Search**                     |       4        |           2            |          2          |
| **Product Reviews & Details**            |       4        |           2            |          2          |
| **Shopping Basket**                      |       4        |           2            |          2          |
| **Address & Delivery**                   |       4        |           1            |          3          |
| **Checkout & Payment**                   |       4        |           1            |          3          |
| **Customer Feedback & Captcha**          |       4        |           2            |          2          |
| **Localization (i18n)**                  |       3        |           1            |          2          |
| **REST API Contracts**                   |       5        |           4            |          1          |
| **Network Resilience & Fault Injection** |       3        |           3            |          0          |
| **Total**                                |     **39**     |         **23**         |       **16**        |

---

## Detailed Scenarios

### 1. User Registration & Identity

| ID             | Title & Description                                                                                                                             | Priority | Decision  |      Tag      |
| :------------- | :---------------------------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-AUTH-01** | **UI Registration of dynamic user**: Register user with email, matching passwords, and security question; verify success redirect and snackbar. |    P1    | Automated |   `@smoke`    |
| **SC-AUTH-02** | **Password mismatch validation**: Verify submit button remains disabled when password and repeat password do not match.                         |    P2    | Automated | `@regression` |
| **SC-AUTH-03** | **Duplicate email rejection**: Attempt registering an already existing email; verify 400 error banner from backend.                             |    P2    |   Later   | `@regression` |
| **SC-AUTH-04** | **API password length enforcement boundary**: Verify backend accepts/rejects short passwords vs UI validation (Documented BUG-001).             |    P2    |  Manual   | `@regression` |

### 2. User Authentication & Session

| ID             | Title & Description                                                                                                           | Priority | Decision  |      Tag      |
| :------------- | :---------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-AUTH-05** | **UI Login with valid credentials**: Login via UI with registered user; verify session tokens stored and redirect to catalog. |    P1    | Automated |   `@smoke`    |
| **SC-AUTH-06** | **UI Login with invalid credentials**: Enter incorrect password; verify 401 error message without session creation.           |    P2    | Automated | `@regression` |
| **SC-AUTH-07** | **API Fast Login via `cy.session`**: Authenticate via `POST /rest/user/login` and cache session state across specs.           |    P2    | Automated | `@regression` |
| **SC-AUTH-08** | **User Logout**: Click account menu and select logout; verify session token is cleared and user reverts to anonymous.         |    P2    |   Later   | `@regression` |

### 3. Product Catalog & Search

| ID            | Title & Description                                                                                                           | Priority | Decision  |      Tag      |
| :------------ | :---------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-CAT-01** | **Search existing product**: Search for "apple" in navbar search bar; verify filtered product cards render.                   |    P1    | Automated |   `@smoke`    |
| **SC-CAT-02** | **Search non-existent product**: Search for "xyznonexistent"; verify empty state card (`.emptyState`) renders.                |    P2    | Automated | `@regression` |
| **SC-CAT-03** | **Catalog pagination**: Switch paginator from 12 to 24 items; verify page size increases and more items render.               |    P3    |   Later   | `@regression` |
| **SC-CAT-04** | **SQL Injection probe in search bar**: Search `' OR 1=1--`; verify application returns all products without SQL syntax error. |    P2    |  Manual   | `@regression` |

### 4. Product Details & Reviews

| ID            | Title & Description                                                                                                 | Priority | Decision  |      Tag      |
| :------------ | :------------------------------------------------------------------------------------------------------------------ | :------: | :-------: | :-----------: |
| **SC-REV-01** | **View product details and reviews**: Click product card; verify modal opens with reviews expansion panel.          |    P2    | Automated | `@regression` |
| **SC-REV-02** | **Submit authenticated product review**: Enter review message as logged-in user and submit; verify review is saved. |    P2    | Automated | `@regression` |
| **SC-REV-03** | **Like a product review**: Click like icon on an existing review; verify like counter increments.                   |    P3    |   Later   | `@regression` |
| **SC-REV-04** | **Review character limit**: Attempt entering review > 160 characters; verify input is truncated at 160 characters.  |    P3    |   Later   | `@regression` |

### 5. Shopping Basket

| ID             | Title & Description                                                                                                         | Priority | Decision  |      Tag      |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-CART-01** | **Add item to basket from catalog**: Click "Add to Basket"; verify API responds 200 and snackbar notification appears.      |    P1    | Automated |   `@smoke`    |
| **SC-CART-02** | **Inspect basket page**: Open `/basket`; verify table rows display item name, price, quantity, and enabled checkout button. |    P2    | Automated | `@regression` |
| **SC-CART-03** | **Increment item quantity in basket**: Click '+' button on basket row; verify quantity and row total update.                |    P2    |   Later   | `@regression` |
| **SC-CART-04** | **Remove line item from basket**: Click delete icon on basket row; verify item is deleted from cart.                        |    P2    |   Later   | `@regression` |

### 6. Address & Delivery Management

| ID             | Title & Description                                                                                                      | Priority | Decision  |      Tag      |
| :------------- | :----------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-ADDR-01** | **Add new shipping address**: Fill Country, Name, Mobile, ZIP, Street, City, State; verify address card created in list. |    P2    | Automated | `@regression` |
| **SC-ADDR-02** | **Required field validation for address**: Leave ZIP code empty; verify form cannot be submitted.                        |    P3    |   Later   | `@regression` |
| **SC-ADDR-03** | **Select delivery speed**: In checkout step 2, select One Day Delivery vs Standard; verify price updates.                |    P2    |   Later   | `@regression` |
| **SC-ADDR-04** | **Delete saved shipping address**: Click delete icon on saved address; verify address card disappears.                   |    P3    |   Later   | `@regression` |

### 7. Checkout & Payment

| ID            | Title & Description                                                                                                                                   | Priority | Decision  |      Tag      |
| :------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-CHK-01** | **End-to-End Checkout Flow**: Complete full journey (Address selection &rarr; Delivery speed &rarr; Card addition &rarr; Review &rarr; Confirmation). |    P1    | Automated |   `@smoke`    |
| **SC-CHK-02** | **Credit card number Luhn algorithm check**: Enter invalid credit card number; verify validation error.                                               |    P2    |   Later   | `@regression` |
| **SC-CHK-03** | **Coupon application in checkout**: Apply valid coupon code; verify discount is reflected on order summary.                                           |    P2    |   Later   | `@regression` |
| **SC-CHK-04** | **Order history verification**: Open `/order-history`; verify placed order appears with receipt download link.                                        |    P2    |   Later   | `@regression` |

### 8. Customer Feedback & Captcha

| ID             | Title & Description                                                                                                        | Priority | Decision  |      Tag      |
| :------------- | :------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-FDBK-01** | **Submit customer feedback**: Enter comment, 5-star rating, and solved captcha; verify feedback saved and snackbar shown.  |    P2    | Automated | `@regression` |
| **SC-FDBK-02** | **Feedback submit button disabled when fields empty**: Verify submit button cannot be clicked without comment and captcha. |    P2    | Automated | `@regression` |
| **SC-FDBK-03** | **Incorrect captcha rejection**: Enter wrong math answer; verify submission is rejected with error.                        |    P3    |   Later   | `@regression` |
| **SC-FDBK-04** | **Anonymous vs logged-in feedback**: Verify author field displays user email when authenticated vs "anonymous".            |    P3    |   Later   | `@regression` |

### 9. Localization (i18n)

| ID             | Title & Description                                                                                                         | Priority | Decision  |      Tag      |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-LANG-01** | **Switch language to German**: Select Deutsch from language menu; verify i18n bundle loaded and labels update (e.g. Konto). |    P2    | Automated | `@regression` |
| **SC-LANG-02** | **Switch language to Spanish**: Select Español; verify navigation items update to Spanish.                                  |    P3    |   Later   | `@regression` |
| **SC-LANG-03** | **Persist selected language on page refresh**: Change language, refresh browser; verify language preference persists.       |    P3    |   Later   | `@regression` |

### 10. REST API Contracts

| ID            | Title & Description                                                                                          | Priority | Decision  |      Tag      |
| :------------ | :----------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-API-01** | **GET /rest/products/search**: Assert 200 OK and product schema keys (`id`, `name`, `price`, `description`). |    P1    | Automated |   `@smoke`    |
| **SC-API-02** | **POST /api/Users**: Assert 201 Created when registering user via API with valid payload.                    |    P2    | Automated | `@regression` |
| **SC-API-03** | **POST /rest/user/login**: Assert 200 OK and verify response contains JWT authentication token and `bid`.    |    P2    | Automated | `@regression` |
| **SC-API-04** | **GET /api/SecurityQuestions**: Assert 200 OK and non-empty array of security questions.                     |    P2    | Automated | `@regression` |
| **SC-API-05** | **GET /rest/admin/application-version**: Assert 200 OK and valid semver version string.                      |    P3    |   Later   |   `@smoke`    |

### 11. Network Resilience & Fault Injection

| ID            | Title & Description                                                                                                            | Priority | Decision  |      Tag      |
| :------------ | :----------------------------------------------------------------------------------------------------------------------------- | :------: | :-------: | :-----------: |
| **SC-NET-01** | **Simulate 500 error on product search**: Intercept `/rest/products/search*` returning 500; verify UI renders gracefully.      |    P2    | Automated | `@regression` |
| **SC-NET-02** | **Simulate 1000ms latency on search**: Intercept with response delay; verify application resolves without crashing.            |    P2    | Automated | `@regression` |
| **SC-NET-03** | **Simulate 500 error on feedback submission**: Intercept `/api/Feedbacks/` returning 500; verify error snackbar shown to user. |    P2    | Automated | `@regression` |
