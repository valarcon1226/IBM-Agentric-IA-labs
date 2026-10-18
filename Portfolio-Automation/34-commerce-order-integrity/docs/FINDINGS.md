# Defects and Vulnerabilities Found in SUT (Saleor 3.20)

This document records real defects found in the System Under Test (SUT) during automated quality and resilience testing.
In accordance with QA policy:
- The SUT is read-only and never patched.
- Defects are logged with exact version, steps, evidence, and severity.
- Corresponding automated tests are marked `@pytest.mark.xfail(strict=True, reason="FINDING-00N")`.

---

## FINDING-001: Concurrency Race Condition in Stock Allocation Causes Inventory Overselling

- **ID:** `FINDING-001`
- **Component:** `saleor.warehouse.management.allocate_stocks` / `saleor.checkout.complete_checkout`
- **SUT Version:** `Saleor 3.20` (image: `ghcr.io/saleor/saleor:3.20`, commit `ffb3e4267c`)
- **Severity:** High (Inventory corruption and financial breach due to unfulfillable orders)
- **Status:** Open / Documented

### Description
Under concurrent checkout completions where 50 buyers race for the last 5 available units of a product variant, Saleor 3.20 allowed up to 8 orders to complete successfully, driving inventory into negative balance (`remaining_stock` down to `-3`). Across 20 test iterations, oversells occurred in 10 runs for a total of 18 oversold units, calculated directly from the database (`quantity_allocated - quantity` per variant).

### Root Cause Analysis
In `saleor/warehouse/management.py` (lines 121–136 of Saleor 3.20 image `ghcr.io/saleor/saleor:3.20`):
```python
    stocks = list(
        stock_select_for_update_for_existing_qs(stocks)
        .filter(**filter_lookup)
        .values("id", "product_variant", "pk", "quantity", "warehouse_id")
    )
    stocks_id = (stock.pop("id") for stock in stocks)

    quantity_reservation_for_stocks: dict = _prepare_stock_to_reserved_quantity_map(
        checkout_lines, check_reservations, stocks_id
    )

    quantity_allocation_list = list(
        Allocation.objects.filter(
            stock_id__in=stocks_id,
            quantity_allocated__gt=0,
        )
...
```
1. `stocks_id` is instantiated as a single-use generator expression `(stock.pop("id") for stock in stocks)`.
2. When `_prepare_stock_to_reserved_quantity_map` evaluates `stocks_id`, the generator is consumed.
3. Subsequent evaluation in `Allocation.objects.filter(stock_id__in=stocks_id)` receives an exhausted generator, generating an empty IN-clause `WHERE stock_id IN ()`.
4. As a result, existing allocations are not calculated into the stock availability check within concurrent worker threads, allowing concurrent transactions to pass validation and allocate stock beyond the warehouse limit.

### Steps to Reproduce
1. In PostgreSQL, configure a product variant with `warehouse_stock.quantity = 5` and `warehouse_stock.quantity_allocated = 0`.
2. Execute 50 simultaneous asynchronous `checkoutCreate` and `checkoutComplete` mutations targeting that variant.
3. Observe the orders and allocations created in database table `warehouse_allocation`.

### Expected Result
- Exactly 5 orders created.
- 45 requests rejected with Saleor error code `INSUFFICIENT_STOCK`.
- Final `warehouse_stock.quantity_allocated = 5` (`remaining_stock = 0`).
- 0 oversells.

### Actual Result
- High concurrency creates between 5 and 8 orders per run on a variant with stock 5.
- Across 20 runs: 18 total oversells occurred in 10 out of the 20 runs, with oversells calculated directly from the database (`quantity_allocated - quantity` per variant).
- Remaining stock dropped to negative values (between -1 and -3).

### Evidence
Log from test execution `tests/resilience/test_stock_race.py`:
```text
Run 01/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 02/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 03/20: orders=8 (expected 5), errors=42 (expected 45), stock=5, allocated=8, remaining_stock=-3, oversells=3
Run 04/20: orders=6 (expected 5), errors=44 (expected 45), stock=5, allocated=6, remaining_stock=-1, oversells=1
Run 05/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 06/20: orders=6 (expected 5), errors=44 (expected 45), stock=5, allocated=6, remaining_stock=-1, oversells=1
Run 07/20: orders=8 (expected 5), errors=42 (expected 45), stock=5, allocated=8, remaining_stock=-3, oversells=3
Run 08/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 09/20: orders=8 (expected 5), errors=42 (expected 45), stock=5, allocated=8, remaining_stock=-3, oversells=3
Run 10/20: orders=7 (expected 5), errors=43 (expected 45), stock=5, allocated=7, remaining_stock=-2, oversells=2
Run 11/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 12/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 13/20: orders=6 (expected 5), errors=44 (expected 45), stock=5, allocated=6, remaining_stock=-1, oversells=1
Run 14/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 15/20: orders=7 (expected 5), errors=43 (expected 45), stock=5, allocated=7, remaining_stock=-2, oversells=2
Run 16/20: orders=6 (expected 5), errors=44 (expected 45), stock=5, allocated=6, remaining_stock=-1, oversells=1
Run 17/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 18/20: orders=6 (expected 5), errors=44 (expected 45), stock=5, allocated=6, remaining_stock=-1, oversells=1
Run 19/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Run 20/20: orders=5 (expected 5), errors=45 (expected 45), stock=5, allocated=5, remaining_stock=0, oversells=0
Total oversells across 20 runs: 18 (in 10 runs)
```

SQL verification query:
```sql
SELECT o.id, ol.variant_id, a.quantity_allocated
FROM order_order o
JOIN order_orderline ol ON ol.order_id = o.id
JOIN warehouse_allocation a ON a.order_line_id = ol.id
WHERE ol.variant_id = 403;
-- Returns 6 rows each with quantity_allocated = 1.
```

### Mitigation
Clients and integrations must implement stock reservations before checkout completion, or implement post-completion allocation reconciliation to flag oversold orders before payment capture.

---

## FINDING-002: productBulkCreate Intra-Batch Duplicate Slug Triggers Unhandled PostgreSQL UniqueViolation (500)

- **ID:** `FINDING-002`
- **Component:** `saleor.graphql.product.bulk_mutations.products.product_bulk_create`
- **SUT Version:** `Saleor 3.20` (image: `ghcr.io/saleor/saleor:3.20`, commit `ffb3e4267c`)
- **Severity:** Medium (Unhandled 500 error aborts entire batch when intra-batch slug collisions occur)
- **Status:** Open / Documented

### Description
When submitting a `productBulkCreate` mutation with `errorPolicy: REJECT_FAILED_ROWS` containing duplicate slugs *within the same batch payload* (intra-batch duplicate), Saleor does not pre-validate duplicate slugs before executing `Product.objects.bulk_create`. This causes an unhandled PostgreSQL integrity error (`psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "product_product_slug_key"`), resulting in an internal server error (HTTP 500) that aborts the entire mutation.

In contrast, when a batch payload contains a slug that duplicates an *already existing record in the database*, Saleor's validator catches it cleanly and returns the expected row-level error with `code: UNIQUE` and `path: slug` under `results[row].errors`.

### Steps to Reproduce
1. Execute `productBulkCreate` with `errorPolicy: REJECT_FAILED_ROWS` and 2 rows sharing the same slug (e.g. `slug: "duplicate-in-batch"`).
2. The mutation fails with a 500 error and GraphQL error: `UniqueViolation: duplicate key value violates unique constraint "product_product_slug_key"`.

### Expected Result
Saleor should detect duplicate slugs within the submitted payload during pre-validation, reject the duplicate row(s) with `code: UNIQUE`, and create the valid rows in accordance with `errorPolicy: REJECT_FAILED_ROWS`.

### Mitigation
Clients sending bulk product imports must deduplicate slugs client-side before dispatching the payload to `productBulkCreate`. Tests targeting duplicate slugs must use slugs that conflict with pre-existing database rows.

