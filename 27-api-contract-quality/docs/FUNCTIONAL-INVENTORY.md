# Functional Inventory — API Contract Quality (Project 27)

This document catalogs all functional surfaces, API endpoints, and contract boundaries under test across the integrated systems.

## 1. System Components under Test

| System Component                | Role              | Protocol / Format        | Source Project                     | Assigned Ports                   |
| ------------------------------- | ----------------- | ------------------------ | ---------------------------------- | -------------------------------- |
| **Web Chat Widget**             | Consumer          | HTTP / JSON              | `22-web-chat-widget`               | Browser runtime                  |
| **Restaurant Assistant API**    | Provider          | HTTP / FastAPI           | `13-whatsapp-restaurant-assistant` | `127.0.0.1:8004` (internal 8000) |
| **Pact Broker & DB**            | Contract Registry | HTTP / PostgreSQL        | `27-api-contract-quality`          | `127.0.0.1:8642` (internal 9292) |
| **E-commerce Order Automation** | Fuzzing Target    | OpenAPI 3.1.0 / FastAPI  | `20-ecommerce-order-automation`    | `127.0.0.1:8000` (internal 8000) |
| **Swagger Petstore v3**         | REST CRUD Target  | OpenAPI 3.0 / Java Jetty | `27-api-contract-quality`          | `127.0.0.1:8643` (internal 8080) |

---

## 2. API Endpoints Inventory

### A. Restaurant Assistant Web Chat (`13-whatsapp-restaurant-assistant`)

- `POST /web/chat`: Primary customer communication channel used by the web widget.
  - **Request Body**: `{ "session_id": string (1-100 chars), "text": string (1-1000 chars) }`
  - **Success Response (200 OK)**: `{ "replies": string[] }`
  - **Client Error (422 Unprocessable Entity)**: Pydantic validation errors when body fields are missing or empty.
  - **Rate Limit (429 Too Many Requests)**: Triggered when a session sends 30+ requests within a 60-second window.
- `GET /health`: Component health status check (`{ "status": "healthy" }`).

### B. E-Commerce Order Automation API (`20-ecommerce-order-automation`)

- `POST /webhooks/shopify`: Webhook ingestion for Shopify order events (HMAC SHA256 verified).
- `POST /webhooks/woocommerce`: Webhook ingestion for WooCommerce order creation (HMAC signature verified).
- `POST /webhooks/stripe`: Webhook ingestion for Stripe payment intent events (Stripe signature verified).
- `GET /admin/orders`: HTML dashboard for order fulfillment triage.
- `POST /admin/orders/{order_id}/status`: Status transition update for order processing.
- `GET /admin/orders/export`: Excel/CSV export of filtered order records.
- `GET /admin/login` / `POST /admin/login`: Admin session authentication.
- `GET /admin/logout`: Session termination.
- `GET /health`: Health and readiness probe.
- `GET /openapi.json`: OpenAPI 3.1.0 specification endpoint.

### C. Swagger Petstore v3 (`swaggerapi/petstore3`)

- **Pet Domain**:
  - `POST /pet`: Add a new pet to the store.
  - `PUT /pet`: Update an existing pet.
  - `GET /pet/{petId}`: Find pet by ID.
  - `GET /pet/findByStatus`: Finds Pets by status (`available`, `pending`, `sold`).
  - `DELETE /pet/{petId}`: Deletes a pet record.
- **Store Domain**:
  - `GET /store/inventory`: Returns pet inventories by status.
  - `POST /store/order`: Place an order for a pet.
  - `GET /store/order/{orderId}`: Find purchase order by ID.
  - `DELETE /store/order/{orderId}`: Delete purchase order by ID.
- **User Domain**:
  - `POST /user`: Create user.
  - `GET /user/{username}`: Get user by user name.
  - `PUT /user/{username}`: Update user.
  - `DELETE /user/{username}`: Delete user.
  - `GET /user/login`: Logs user into the system.
  - `GET /user/logout`: Logs out current logged in user session.

---

## 3. Contract Boundaries

```
[22-web-chat-widget]
      │ (Pact Consumer Test: chat-widget.spec.ts)
      ▼
[Pact File: WebChatWidget-RestaurantAssistantAPI.json]
      │ (publish:pact)
      ▼
[Pact Broker @ 127.0.0.1:8642]
      ▲ (can-i-deploy gate)
      │ (verify:provider)
[13-whatsapp-restaurant-assistant @ 127.0.0.1:8004]
```
