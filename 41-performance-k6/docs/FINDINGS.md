# Findings in the system under test

This document records real defects and performance bottlenecks observed in the System Under Test (`20-ecommerce-order-automation`) under automated load conditions.

---

### FINDING-001: Race Condition on Concurrent Deliveries of the Same Webhook Order Causes HTTP 500

- **Component:** `app.routes.webhooks.receive_woocommerce_webhook` / `app.database.MongoRepository.create_order`
- **Severity:** Medium
- **Status:** Fixed in project 20 (commit `736cc86`). After the fix `scripts/repro_duplicate_race.py` returns HTTP 200 for all 40 deliveries, 10 orders are stored and 10 emails are sent. The description below is the behaviour before the fix.

#### Description
When multiple webhook deliveries for the same order arrive simultaneously, a race condition occurs between the duplicate event check and the order insertion in MongoDB.

In `app/routes/webhooks.py`:
- Lines 66-74 check whether the event is already recorded and processed via `existing_event = await repo.get_event(event_id, payload_hash)` and `if existing_event and existing_event.processed: return {"status": "ignored", "reason": "duplicate_event"}`.
- Line 83 creates the event record (`await repo.create_event(event_record)`).
- Line 87 attempts to persist the order: `await repo.create_order(order)`.
- Line 94 marks the event as processed: `await repo.mark_event_processed(event_id, order.id)`.

In `app/database.py`:
- Line 166 establishes the unique index on order id: `await self.db.orders.create_index("id", unique=True)`.
- Lines 211-213 execute the insert:
  ```python
  async def create_order(self, order: Order) -> Order:
      await self.db.orders.insert_one(order.model_dump())
      return order
  ```
- Lines 242-246 query events by `event_id` or `payload_hash`:
  ```python
  async def get_event(self, event_id: str, payload_hash: str) -> Optional[WebhookEvent]:
      doc = await self.db.events.find_one(
          {"$or": [{"event_id": event_id}, {"payload_hash": payload_hash}]}
      )
      return WebhookEvent(**doc) if doc else None
  ```

#### What Works
- **Sequential Re-delivery:** A sequential re-delivery of the same order (even with a different `x-wc-webhook-id`) correctly returns HTTP 200 with `{"status": "ignored", "reason": "duplicate_event"}`. Because the payload hash is identical and the initial request completed line 94 (`mark_event_processed`), lines 66-74 detect `existing_event.processed == True` and short-circuit.
- **Database Integrity:** The unique index `id_1` on the `orders` collection (`app/database.py`, line 166) functions as designed and successfully prevents duplicate order documents from being persisted.

#### Failure Under Concurrent Execution
When deliveries for the same order arrive at the same time, multiple requests execute the check at lines 66-67 before the first request reaches line 94 (`mark_event_processed`). Both pass the idempotency guard and call `await repo.create_order(order)` (line 87). The first request inserts the order document. The concurrent request attempts `insert_one` on line 212 of `app/database.py`, triggering `pymongo.errors.DuplicateKeyError`. Because this exception is not caught, FastAPI/Starlette responds with HTTP 500 Internal Server Error.

#### Reproduction Output (`scripts/repro_duplicate_race.py`)
```text
10 orders x 4 simultaneous deliveries
HTTP 200: 11
HTTP 500: 29
```

#### Traceback from Container Logs (`docker logs cafe_perf_api`)
```text
  File "/app/app/routes/webhooks.py", line 87, in receive_woocommerce_webhook
    await repo.create_order(order)
  File "/app/app/database.py", line 212, in create_order
    await self.db.orders.insert_one(order.model_dump())
...
pymongo.errors.DuplicateKeyError: E11000 duplicate key error collection: cafe_perf.orders index: id_1 dup key: { id: "ORD-WC-68703868" }, full error: {'index': 0, 'code': 11000, 'errmsg': 'E11000 duplicate key error collection: cafe_perf.orders index: id_1 dup key: { id: "ORD-WC-68703868" }', 'keyPattern': {'id': 1}, 'keyValue': {'id': 'ORD-WC-68703868'}}
```
