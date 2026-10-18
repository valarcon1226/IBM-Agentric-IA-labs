# Risk Analysis — E-Commerce Order Integrity (Saleor)

This risk matrix evaluates operational, data integrity, and business failure modes for Saleor e-commerce.

## Risk Scoring Formula

- **Likelihood (L):** 1 (rare) to 5 (almost certain under production load or network churn).
- **Impact (I):** 1 (negligible) to 5 (catastrophic revenue/inventory loss or data corruption).
- **Risk Score:** $R = L \times I$.
- **Risk Tiers:**
  - **High ($R \ge 15$):** Mandatory PR gate tests marked with `@pytest.mark.p1`.
  - **Medium ($8 \le R < 15$):** Nightly or specialized test suites (`resilience`, `migration`, `perf`).
  - **Low ($R < 8$):** Smoke tests, documentation, or periodic checks.

## Risk Evaluation Matrix

| Area | Risk Description | Likelihood (L) | Reason (L) | Impact (I) | Reason (I) | Risk ($L \times I$) | Tier | Marker |
|------|------------------|----------------|------------|------------|------------|---------------------|------|--------|
| **Stock** | Concurrent checkout race conditions cause overselling below zero inventory | 4 | Flash sales and high-concurrency traffic drive simultaneous allocations | 5 | Selling unfulfillable stock breaches customer trust and requires manual cancellations | **20** | High | `p1`, `resilience` |
| **Checkout** | Client retry after network drop creates duplicate orders for a single cart | 4 | Unstable mobile clients automatically re-submit unacknowledged checkouts | 5 | Duplicate orders cause duplicate charges and inventory shrinkage | **20** | High | `p1`, `resilience` |
| **Webhooks** | Slow or failing consumer drops events or introduces excessive delivery lag | 4 | Downstream ERP or logistics endpoints experience transient downtime or 500s | 4 | Missed order-created events delay fulfillment and disrupt inventory reconciliation | **16** | High | `p1`, `resilience` |
| **Catalog Listing** | Cursor pagination drops or duplicates products during catalog browsing/indexing | 3 | Real-time catalog updates and high first limits can distort cursor boundaries | 4 | Missing items reduce sales and duplicate items corrupt ingestion pipelines | **12** | Medium | `p1`, `perf` |
| **Bulk Import** | `productBulkCreate` partial failure leaves half-created entities or corrupt IDs | 3 | Large supplier catalog feeds frequently contain malformed rows or slug collisions | 4 | Orphaned database records and broken product-variant foreign keys | **12** | Medium | `p1` |
| **Upgrade** | Schema and data migrations between minor versions corrupt financial/order checksums | 2 | Official releases migrate order models, lines, and tax structures | 5 | Ledger discrepancies, historical order loss, and reporting distortion | **10** | Medium | `migration` |
| **Payment Transactions** | Partial payment/refund desynchronization between staff dashboard and backend ledger | 2 | Staff manual adjustments and refund operations during order lifecycle | 4 | Financial auditing discrepancies and customer billing complaints | **8** | Medium | `ui` |

## High-Risk Coverage Summary

Every High-Risk area ($R \ge 15$) is directly mapped to automated test suites in `tests/`:
1. **Stock ($R=20$):** `tests/resilience/test_stock_race.py` (50 concurrent buyers, 20 race runs).
2. **Checkout ($R=20$):** `tests/resilience/test_client_retry.py` (Toxiproxy connection cut, idempotency validation, 50 retries).
3. **Webhooks ($R=16$):** `tests/resilience/test_webhooks.py` (500 orders through slow consumer + 30% failure injection).
