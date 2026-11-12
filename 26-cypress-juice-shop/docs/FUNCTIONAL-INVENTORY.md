# Functional Inventory — OWASP Juice Shop

## 1. System Overview

OWASP Juice Shop is an intentionally insecure, feature-complete modern web application modeling an e-commerce platform for fruit juices and related merchandise. Built on an Angular SPA frontend, an Express.js / Node.js backend, and a SQLite / Sequelize relational database, it represents a rich target for both functional quality assurance and application security testing.

---

## 2. Module Inventory

### M01: User Authentication & Identity Management

- **User Registration (`/#/register`)**: Form with email, password, repeat password, security question selection, and security answer. Backend endpoint: `POST /api/Users/`.
- **User Login (`/#/login`)**: Form with email and password, "Remember Me" toggle, and OAuth option. Backend endpoint: `POST /rest/user/login` returning signed JWT and basket identifier (`bid`).
- **Session Handling**: JWT token persistence in `localStorage`, basket identification in `sessionStorage`, role-based access token verification on authenticated routes.
- **Security Questions (`GET /api/SecurityQuestions/`)**: System question catalog used for account password recovery.
- **User Profile & Logout (`/#/profile`)**: Viewing user details, updating username, uploading profile images, and revoking active sessions.

### M02: Product Catalog & Search

- **Catalog Grid (`/#/search`)**: Responsive grid displaying products (`Apple Juice`, `Orange Juice`, `Eggfruit Juice`, merchandise). Backend endpoint: `GET /rest/products/search?q=`.
- **Search Bar (`#searchQuery`)**: Dynamic keyword search filtering product cards client-side via Angular `MatTableDataSource` and route query parameter binding (`q=<query>`).
- **Empty State**: Friendly fallback card (`.emptyState`) displayed when no matching products exist.
- **Paginator**: Page size selection (12, 24, 36 items) and pagination navigation.

### M03: Product Reviews & Social Proof

- **Product Details Modal (`mat-dialog-container`)**: Opened by clicking on any product card; displays full description, price, and image.
- **Review List**: Expansion panel displaying community reviews fetched via `GET /rest/products/:id/reviews`.
- **Submit Review**: Form allowing authenticated users to post feedback reviews up to 160 characters via `PUT /rest/products/:id/reviews`.
- **Like / Dislike**: Interactivity allowing users to vote on reviews via `POST /rest/products/reviews/like`.

### M04: Shopping Basket Management

- **Add to Basket**: One-click action from catalog cards (`btn-basket`). Backend endpoint: `POST /api/BasketItems/`.
- **Basket Inspection (`/#/basket`)**: Itemized table showing product thumbnail, name, unit price, quantity increment/decrement controls, total item price, and aggregate checkout subtotal.
- **Item Removal**: Delete button allowing line items to be removed from the active basket.
- **Coupon Application**: Input field for promotional voucher codes.

### M05: Address & Delivery Management

- **Saved Addresses (`/#/address/saved`)**: List of previously registered shipping addresses.
- **Address Creation (`/#/address/create`)**: Form validating Country, Name, Mobile Number, ZIP Code, Street Address, City, and State. Backend endpoint: `POST /api/Addresss/`.
- **Address Selection Wizard (`/#/address/select`)**: Step 1 of checkout allowing delivery destination selection.
- **Delivery Method Selection (`/#/delivery-method`)**: Step 2 of checkout selecting shipping carrier speed (One Day Delivery, Fast Delivery, Standard Delivery) via `GET /api/Deliverys`.

### M06: Payment & Order Processing

- **Saved Cards (`/#/saved-payment-methods`)**: View and manage saved credit/debit cards.
- **Card Registration**: Form modal validating Cardholder Name, 16-digit Card Number, Expiration Month (1–12), and Expiration Year. Backend endpoint: `POST /api/Cards/`.
- **Payment Method Selection (`/#/payment/shop`)**: Step 3 of checkout selecting active payment method or digital wallet balance.
- **Order Summary (`/#/order-summary`)**: Step 4 of checkout displaying line items, shipping address, delivery method, payment method, tax calculations, and final total.
- **Checkout Finalization**: Backend checkout trigger `POST /rest/basket/:bid/checkout`.
- **Order Confirmation (`/#/order-completion/:id`)**: Completion receipt screen with confirmation message, order reference, and PDF invoice generation link.

### M07: Customer Feedback & Captcha Verification

- **Customer Feedback Form (`/#/contact`)**: Form with author identifier, multiline comment box, 5-star rating slider, and mathematical challenge captcha. Backend endpoint: `POST /api/Feedbacks/`.
- **Dynamic Captcha (`GET /rest/captcha/`)**: Math equation generator preventing automated spam.

### M08: Localization & Internationalization (i18n)

- **Language Menu**: Selection dropdown in top navigation offering English, German, Spanish, French, Chinese, and other locales.
- **Dynamic Asset Loading**: Asynchronous fetch of translation JSON dictionaries (`GET /assets/i18n/{locale}.json`).
- **Reactive UI Re-rendering**: Instant translation of navbar, buttons, snackbars, and form labels.

### M09: REST API Interface

- **Public Endpoints**: `/rest/products/search`, `/api/SecurityQuestions/`, `/rest/admin/application-version`.
- **Authentication Endpoints**: `POST /api/Users/`, `POST /rest/user/login`.
- **Authenticated CRUD Endpoints**: `/api/BasketItems/`, `/api/Addresss/`, `/api/Cards/`, `/rest/products/:id/reviews`, `/rest/basket/:id/checkout`.

---

## 3. User Roles & Permissions

| Role                    | Permissions & Scope                                                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Anonymous / Guest**   | Browse catalog, search products, view reviews, change language, register account, log in, submit contact feedback.                             |
| **Registered Customer** | All guest capabilities plus add to basket, manage personal addresses, manage payment cards, post reviews, complete orders, view order history. |
| **Deluxe Customer**     | All customer capabilities plus discounted pricing (`deluxePrice`), fast-track delivery, and exclusive merchandise access.                      |
| **Administrator**       | Access to administrative dashboard, all user baskets, system logs, challenge configuration, and product management.                            |
