# Traceability Matrix — Risk & Requirements to Test Implementation

This matrix establishes end-to-end bidirectional traceability from identified business and architectural risks (`RISK-ANALYSIS.md`) through functional test scenarios (`TEST-SCENARIOS.md`) to automated Cypress test specifications.

| Risk ID    | Risk Category     | Scenario ID    | Scenario Summary                         | Spec File                                                      |        Status         |
| :--------- | :---------------- | :------------- | :--------------------------------------- | :------------------------------------------------------------- | :-------------------: |
| **RSK-01** | Security / Auth   | **SC-AUTH-01** | UI Registration of dynamic user          | `cypress/e2e/01-auth/registration.cy.ts`                       |     **Automated**     |
| **RSK-01** | Security / Auth   | **SC-AUTH-02** | Password mismatch form validation        | `cypress/e2e/01-auth/registration.cy.ts`                       |     **Automated**     |
| **RSK-01** | Security / Auth   | **SC-AUTH-03** | Duplicate email rejection                | —                                                              |   _Not Implemented_   |
| **RSK-01** | Security / Auth   | **SC-AUTH-04** | API password length bypass (BUG-001)     | —                                                              | _Manual (Documented)_ |
| **RSK-02** | Security / Auth   | **SC-AUTH-05** | UI Login with valid credentials          | `cypress/e2e/01-auth/login.cy.ts`                              |     **Automated**     |
| **RSK-02** | Security / Auth   | **SC-AUTH-06** | UI Login rejection on invalid password   | `cypress/e2e/01-auth/login.cy.ts`                              |     **Automated**     |
| **RSK-02** | Security / Auth   | **SC-AUTH-07** | API session caching via `cy.session`     | `cypress/e2e/01-auth/login.cy.ts`                              |     **Automated**     |
| **RSK-02** | Security / Auth   | **SC-AUTH-08** | Session logout and token clearance       | —                                                              |   _Not Implemented_   |
| **RSK-03** | Security / Data   | **SC-API-03**  | Sensitive token and claim validation     | `cypress/e2e/05-api/api-rest.cy.ts`                            |     **Automated**     |
| **RSK-04** | Resilience        | **SC-NET-01**  | Fault injection: 500 on product search   | `cypress/e2e/06-network-resilience/intercept-resilience.cy.ts` |     **Automated**     |
| **RSK-04** | Resilience        | **SC-NET-03**  | Fault injection: 500 on feedback submit  | `cypress/e2e/06-network-resilience/intercept-resilience.cy.ts` |     **Automated**     |
| **RSK-05** | Core / Checkout   | **SC-CHK-01**  | End-to-End full checkout purchase flow   | `cypress/e2e/03-cart-checkout/checkout-flow.cy.ts`             |     **Automated**     |
| **RSK-05** | Core / Checkout   | **SC-CHK-02**  | Credit card Luhn validation              | —                                                              |   _Not Implemented_   |
| **RSK-05** | Core / Checkout   | **SC-CHK-03**  | Coupon code discount application         | —                                                              |   _Not Implemented_   |
| **RSK-05** | Core / Checkout   | **SC-CHK-04**  | Order history and invoice download       | —                                                              |   _Not Implemented_   |
| **RSK-06** | Core / Cart       | **SC-CART-01** | Add product to basket from catalog       | `cypress/e2e/03-cart-checkout/cart-management.cy.ts`           |     **Automated**     |
| **RSK-06** | Core / Cart       | **SC-CART-02** | Basket inspection and table totals       | `cypress/e2e/03-cart-checkout/cart-management.cy.ts`           |     **Automated**     |
| **RSK-06** | Core / Cart       | **SC-CART-03** | Item quantity increment in basket        | —                                                              |   _Not Implemented_   |
| **RSK-06** | Core / Cart       | **SC-CART-04** | Line item deletion from basket           | —                                                              |   _Not Implemented_   |
| **RSK-06** | Core / Address    | **SC-ADDR-01** | Add new shipping address via form        | `cypress/e2e/03-cart-checkout/address-management.cy.ts`        |     **Automated**     |
| **RSK-06** | Core / Address    | **SC-ADDR-02** | Required field address validation        | —                                                              |   _Not Implemented_   |
| **RSK-06** | Core / Address    | **SC-ADDR-03** | Delivery method speed selection          | —                                                              |   _Not Implemented_   |
| **RSK-06** | Core / Address    | **SC-ADDR-04** | Saved address deletion                   | —                                                              |   _Not Implemented_   |
| **RSK-07** | Resilience        | **SC-NET-02**  | Latency injection: 1000ms delayed search | `cypress/e2e/06-network-resilience/intercept-resilience.cy.ts` |     **Automated**     |
| **RSK-08** | UX / Feedback     | **SC-FDBK-01** | Submit customer feedback with captcha    | `cypress/e2e/04-interactions/customer-feedback.cy.ts`          |     **Automated**     |
| **RSK-08** | UX / Feedback     | **SC-FDBK-02** | Feedback submit disabled on empty fields | `cypress/e2e/04-interactions/customer-feedback.cy.ts`          |     **Automated**     |
| **RSK-08** | UX / Feedback     | **SC-FDBK-03** | Math captcha incorrect answer rejection  | —                                                              |   _Not Implemented_   |
| **RSK-08** | UX / Feedback     | **SC-FDBK-04** | Author display based on session          | —                                                              |   _Not Implemented_   |
| **RSK-09** | Localization      | **SC-LANG-01** | Language switch to German (de_DE)        | `cypress/e2e/04-interactions/language-switch.cy.ts`            |     **Automated**     |
| **RSK-09** | Localization      | **SC-LANG-02** | Language switch to Spanish (es_ES)       | —                                                              |   _Not Implemented_   |
| **RSK-09** | Localization      | **SC-LANG-03** | Persistence of language on reload        | —                                                              |   _Not Implemented_   |
| **RSK-10** | Search / Catalog  | **SC-CAT-01**  | Search existing product ("apple")        | `cypress/e2e/02-catalog/search-and-filter.cy.ts`               |     **Automated**     |
| **RSK-10** | Search / Catalog  | **SC-CAT-02**  | Search non-existent product empty state  | `cypress/e2e/02-catalog/search-and-filter.cy.ts`               |     **Automated**     |
| **RSK-10** | Search / Catalog  | **SC-CAT-03**  | Catalog paginator page size change       | —                                                              |   _Not Implemented_   |
| **RSK-10** | Search / Catalog  | **SC-CAT-04**  | SQLi input probe verification            | —                                                              | _Manual (Documented)_ |
| **RSK-10** | Reviews           | **SC-REV-01**  | View product reviews modal               | `cypress/e2e/02-catalog/product-reviews.cy.ts`                 |     **Automated**     |
| **RSK-10** | Reviews           | **SC-REV-02**  | Submit authenticated product review      | `cypress/e2e/02-catalog/product-reviews.cy.ts`                 |     **Automated**     |
| **RSK-10** | Reviews           | **SC-REV-03**  | Like an existing review                  | —                                                              |   _Not Implemented_   |
| **RSK-10** | Reviews           | **SC-REV-04**  | Review character length boundary (160)   | —                                                              |   _Not Implemented_   |
| **N/A**    | REST API Contract | **SC-API-01**  | Product search schema validation         | `cypress/e2e/05-api/api-rest.cy.ts`                            |     **Automated**     |
| **N/A**    | REST API Contract | **SC-API-02**  | User registration endpoint contract      | `cypress/e2e/05-api/api-rest.cy.ts`                            |     **Automated**     |
| **N/A**    | REST API Contract | **SC-API-04**  | Security questions endpoint contract     | `cypress/e2e/05-api/api-rest.cy.ts`                            |     **Automated**     |
