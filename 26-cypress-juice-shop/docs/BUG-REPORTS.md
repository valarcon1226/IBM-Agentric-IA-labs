# Defect & Vulnerability Reports — OWASP Juice Shop

All defect reports below were directly reproduced, captured, and validated against the local containerized System Under Test (`bkimminich/juice-shop:v17.1.1` on `127.0.0.1:8641`).

---

## BUG-001: Backend REST API Accepts Single-Character Password Bypassing UI Policy

- **Bug ID**: `BUG-001`
- **Severity**: High / Major
- **Classification**: CWE-521 (Weak Password Requirements) · CWE-1025 (Inconsistent Validation)
- **Component**: User Registration (`POST /api/Users/`)
- **Environment**: Local Docker (`v17.1.1`), Windows 11, Node v20.17.0

### Description

The Angular frontend registration form enforces a strict minimum password length requirement of 5 characters, disabling the submit button (`#registerButton`) if shorter. However, the backend REST API endpoint `POST /api/Users/` performs zero length, complexity, or entropy checks, accepting a 1-character password (`"1"`) and returning HTTP 201 Created.

### Steps to Reproduce

1. Send an HTTP POST request to `http://127.0.0.1:8641/api/Users/` with a 1-character password:
   ```json
   {
     "email": "short_pwd_test@example.com",
     "password": "1",
     "securityQuestion": { "id": 1 },
     "securityAnswer": "test"
   }
   ```
2. Inspect the HTTP status code and response payload.

### Expected Result

The backend API should reject the request with `HTTP 400 Bad Request` or `HTTP 422 Unprocessable Entity` stating that the password does not meet minimum security length policy (e.g. at least 8 characters).

### Actual Result & Real Evidence

The server responds with `HTTP/1.1 201 Created` and successfully stores the user:

```json
{
  "status": "success",
  "data": {
    "username": "",
    "role": "customer",
    "deluxeToken": "",
    "lastLoginIp": "0.0.0.0",
    "profileImage": "/assets/public/images/uploads/default.svg",
    "isActive": true,
    "id": 22,
    "email": "short_pwd_test@example.com",
    "updatedAt": "2026-10-16T03:42:53.101Z",
    "createdAt": "2026-10-16T03:42:53.101Z",
    "deletedAt": null
  }
}
```

---

## BUG-002: Broken Object-Level Authorization (BOLA/IDOR) on Shopping Cart Retrieval

- **Bug ID**: `BUG-002`
- **Severity**: Critical
- **Classification**: CWE-639 (Insecure Direct Object Reference) · OWASP API Security Top 10 API1:2023 (BOLA)
- **Component**: Basket Service (`GET /rest/basket/:id`)
- **Environment**: Local Docker (`v17.1.1`), Windows 11

### Description

Any authenticated user can inspect the shopping cart contents of any other user in the database (including administrators) simply by changing the numeric ID in the URL parameter `/rest/basket/:id`. The backend checks that an `Authorization: Bearer <token>` header exists, but fails to check that the requesting user owns the requested basket.

### Steps to Reproduce

1. Register and log in as normal customer User A (`id: 22`, whose basket is `6`).
2. Extract User A's JWT token from `/rest/user/login`.
3. Send a GET request to `/rest/basket/1` (which belongs to the Administrator `UserId: 1`), providing User A's token:
   ```http
   GET /rest/basket/1 HTTP/1.1
   Host: 127.0.0.1:8641
   Authorization: Bearer <User_A_Token>
   ```

### Expected Result

The server should respond with `HTTP 403 Forbidden` rejecting access to another user's cart.

### Actual Result & Real Evidence

The server returns `HTTP 200 OK` exposing all products, quantities, and prices in Administrator's cart:

```json
{
  "status": "success",
  "data": {
    "id": 1,
    "coupon": null,
    "UserId": 1,
    "createdAt": "2026-10-16T03:42:16.294Z",
    "updatedAt": "2026-10-16T03:42:16.294Z",
    "Products": [
      {
        "id": 1,
        "name": "Apple Juice (1000ml)",
        "price": 1.99,
        "BasketItem": { "ProductId": 1, "BasketId": 1, "id": 1, "quantity": 2 }
      },
      {
        "id": 2,
        "name": "Orange Juice (1000ml)",
        "price": 2.99,
        "BasketItem": { "ProductId": 2, "BasketId": 1, "id": 2, "quantity": 3 }
      }
    ]
  }
}
```

---

## BUG-003: Sensitive Password Hash Leaked in Authentication JWT Claims

- **Bug ID**: `BUG-003`
- **Severity**: Critical
- **Classification**: CWE-312 (Cleartext Storage of Sensitive Information) · CWE-328 (Reversible / Weak Hash) · OWASP Top 10 A02:2021 (Cryptographic Failures)
- **Component**: Authentication Service (`POST /rest/user/login`)
- **Environment**: Local Docker (`v17.1.1`)

### Description

Upon successful login, the server issues a JSON Web Token (JWT). The token payload claims contain a complete serialization of the user database row, including the password hash (`data.password`). Furthermore, the password hash is computed using unsalted MD5 (`c4ca4238a0b923820dcc509a6f75849b` for password `"1"`), allowing instantaneous rainbow-table reversal.

### Steps to Reproduce

1. Log in via `POST /rest/user/login`.
2. Base64-decode the second segment (claims payload) of the returned JWT token.

### Expected Result

JWT claims should only contain identity and authorization claims (`sub`, `email`, `role`, `exp`, `iat`). Password hashes must never be serialized into client-accessible tokens.

### Actual Result & Real Evidence

Decoded JWT header and payload:

```json
{
  "status": "success",
  "data": {
    "id": 22,
    "email": "short_pwd_test@example.com",
    "password": "c4ca4238a0b923820dcc509a6f75849b",
    "role": "customer",
    "deluxeToken": "",
    "isActive": true
  },
  "iat": 1792122193
}
```

---

## BUG-004: Unhandled Unique Constraint Database Exception Leaks Full Stack Trace in HTML Response

- **Bug ID**: `BUG-004`
- **Severity**: Medium
- **Classification**: CWE-209 (Generation of Error Message Containing Sensitive Information)
- **Component**: Basket Item Creation (`POST /api/BasketItems/`)
- **Environment**: Local Docker (`v17.1.1`)

### Description

When an item is added to the shopping basket that already exists for that `BasketId`, the SQLite Sequelize layer triggers a unique constraint violation on `(ProductId, BasketId)`. Rather than handling this error and returning an appropriate `409 Conflict` or updating the quantity, Express throws an unhandled exception that renders a full HTML stack trace exposing filesystem paths and dependency versions.

### Steps to Reproduce

1. Add Product 1 to Basket 1 via `POST /api/BasketItems/`.
2. Send a second `POST /api/BasketItems/` with identical `ProductId: 1` and `BasketId: 1`.

### Expected Result

The backend should catch the constraint violation and either update quantity or return `HTTP 409 Conflict` with a JSON formatted error response.

### Actual Result & Real Evidence

The server crashes the request, returning `HTTP/1.1 500 Internal Server Error` with HTML rendering:

```html
<div id="wrapper">
  <h1>OWASP Juice Shop (Express ^4.17.1)</h1>
  <h2><em>500</em> Error</h2>
  <ul id="stacktrace">
    <li>at Database.<anonymous> (/juice-shop/node_modules/sequelize/lib/dialects/sqlite/query.js:185:27)</li>
    <li>at async SQLiteQueryInterface.insert (/juice-shop/node_modules/sequelize/lib/dialects/abstract/query-interface.js:308:21)</li>
    <li>at async BasketItem.save (/juice-shop/node_modules/sequelize/lib/model.js:2490:35)</li>
  </ul>
</div>
```
