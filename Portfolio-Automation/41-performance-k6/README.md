# Project 41: E-Commerce Performance & Regression Gate Suite (k6)

Performance testing and regression gate suite for the **Café de Origen E-Commerce Automation** service (FastAPI + MongoDB + Mailpit) using **k6 v2.3.0**.

---

## 1. System Under Test (SUT)

The harness binds strictly to `127.0.0.1` and runs containerized alongside the mail mock and database:

| Service | Pinned Image / Version | Port | Description |
|---|---|---|---|
| **API (`api`)** | Built from `../20-ecommerce-order-automation` (Python 3.12-slim) | `127.0.0.1:8000` | FastAPI order processing service, webhook ingestion, HMAC validation, and Jinja2 admin portal. |
| **Database (`mongo`)** | `mongo:7.0.8` | `127.0.0.1:27017` | Order store and webhook event idempotency ledger. |
| **Mail Mock (`mailpit`)** | `axllent/mailpit:v1.21` | `127.0.0.1:1025`, `127.0.0.1:8025` | Local SMTP mock for order dispatch notifications. |
| **Load Generator** | `grafana/k6:2.3.0` | Containerized | Go-based load generator executing JavaScript scenarios with native crypto module. |

---

## 2. Test Scenarios and Threshold Rationales

The suite exercises four performance profiles:

| Scenario | Script | Concurrency & Profile | Workload Description | Target SLA Thresholds & Rationale |
|---|---|---|---|---|
| **Smoke** | `k6/smoke.js` | 1 VU, 30 s duration | Sequential health check (`GET /health`) and valid WooCommerce webhook processing. | • `http_req_duration`: p95 < 300 ms<br>• `endpoint:health`: p95 < 150 ms<br>• `endpoint:webhook_woocommerce`: p95 < 300 ms<br>• `http_req_failed`: rate < 1%<br>• `checks`: rate > 99%<br>*Rationale:* Verifies basic connectivity and HMAC signature verification without concurrency. |
| **Load (Baseline)** | `k6/load.js` | Ramp up to 20 VUs over 2 min (30s ramp-up, 60s steady, 30s ramp-down) | 45% WooCommerce webhooks, 45% Shopify webhooks (unique order IDs and HMAC signatures), 10% admin flow (CSRF token, login, orders list). | • `http_req_duration`: p95 < 600 ms<br>• `endpoint:webhook_woocommerce`: p95 < 500 ms<br>• `endpoint:webhook_shopify`: p95 < 500 ms<br>• `endpoint:admin_orders`: p95 < 600 ms<br>• `http_req_failed`: rate < 2%<br>• `checks`: rate > 98%<br>*Rationale:* Simulates peak shopping traffic while staff views orders. |
| **Spike** | `k6/spike.js` | Jump to 60 VUs in 5 s, sustained for 20 s, ramp-down in 5 s | Concurrent burst of orders split equally between WooCommerce and Shopify webhooks. | • `http_req_duration`: p95 < 1,500 ms<br>• `endpoint:webhook_*`: p95 < 1,500 ms<br>• `http_req_failed`: rate < 5%<br>• `checks`: rate > 95%<br>*Rationale:* Tests connection handling under sudden traffic spikes. |
| **Negative Security** | `k6/negative.js` | 5 VUs, 30 s duration | Submission of forged HMAC-SHA256 signatures (`x-wc-webhook-signature` and `X-Shopify-Hmac-Sha256`). | • `checks`: rate == 100% (strictly 401)<br>• `http_req_failed`: rate == 0% (401 registered as expected)<br>• `http_req_duration`: p95 < 200 ms<br>*Rationale:* Confirms invalid signatures are rejected before database access. |

---

## 3. Measured Performance SLA & Benchmark Results

> **Environment:** Windows 11 laptop, 16 cores, 32 GB RAM, Docker Desktop. Recorded on **2026-11-10**.
> 
> *Baseline:* `baseline.json` is the load summary of [CI run 42955293380](https://github.com/valarcon1226/qa-automation-portfolio/actions/runs/42955293380) on a GitHub-hosted `ubuntu-latest` runner (overall p95 366.05 ms, 1,472 requests, no failed requests). The first CI run compared against the laptop baseline and failed the gate at +106%: the runner is about twice as slow as the laptop, so a baseline only means something on the hardware that produced it. The table below is the laptop run.

| Scenario / Target | Target Threshold | Measured Value (Local 2026-11-10) | Result |
|---|---|---|:---:|
| **Smoke: Overall p95 latency** | ≤ 300.00 ms | **15.45 ms** (avg: 8.71 ms, p90: 13.48 ms) | PASS |
| **Smoke: `GET /health` p95** | ≤ 150.00 ms | **3.12 ms** (avg: 2.36 ms, p90: 2.92 ms) | PASS |
| **Smoke: WooCommerce webhook p95** | ≤ 300.00 ms | **17.72 ms** (avg: 15.05 ms, p90: 15.53 ms) | PASS |
| **Smoke: Error rate & checks** | Error < 1%, Checks > 99% | **0.00% errors** (0/60 reqs), **100.00% checks** (120/120) | PASS |
| **Load: Overall p95 latency** | ≤ 600.00 ms | **177.36 ms** (avg: 46.82 ms, p90: 115.91 ms) | PASS |
| **Load: WooCommerce webhook p95** | ≤ 500.00 ms | **125.55 ms** (avg: 32.90 ms, p90: 90.81 ms) | PASS |
| **Load: Shopify webhook p95** | ≤ 500.00 ms | **116.90 ms** (avg: 32.15 ms, p90: 89.02 ms) | PASS |
| **Load: Admin `/admin/orders` p95** | ≤ 600.00 ms | **437.74 ms** (avg: 188.94 ms, p90: 306.56 ms) | PASS |
| **Load: Total throughput** | — | **1,513 requests** in 120 s (12.53 req/s), 1,275 iterations | PASS |
| **Load: Error rate & checks** | Error < 2%, Checks > 98% | **0.00% errors** (0/1,513 reqs), **100.00% checks** (2,669/2,669) | PASS |
| **Spike: Overall p95 (60 VUs)** | ≤ 1,500.00 ms | **69.91 ms** (avg: 25.21 ms, p90: 54.30 ms) | PASS |
| **Spike: Peak throughput** | — | **2,886 requests** in 30 s (**94.78 req/s**) | PASS |
| **Spike: Error rate & checks** | Error < 5%, Checks > 95% | **0.00% errors** (0/2,886 reqs), **100.00% checks** (5,772/5,772) | PASS |
| **Negative: Invalid signature rejection** | 100% rejected with 401 | **100.00%** (600/600 rejected with HTTP 401) | PASS |
| **Negative: Defense duration p95** | ≤ 200.00 ms | **4.45 ms** (avg: 2.82 ms, p90: 4.11 ms) | PASS |

### Load Run Variance & CI Gate Rationale

Three consecutive runs of `load.js` under identical conditions produced the following p95 figures:

| Metric / Endpoint | Run 1 p95 (ms) | Run 2 p95 (ms, Median) | Run 3 p95 (ms) | Difference (Max - Min) | % Delta |
|---|---:|---:|---:|---:|---:|
| `http_req_duration` (overall) | 138.19 | 177.36 | 181.62 | +43.43 ms | +31.43% |
| `admin_orders` | 342.44 | 437.74 | 346.16 | +95.30 ms | +27.83% |
| `webhook_shopify` | 100.33 | 116.90 | 115.77 | +16.57 ms | +16.52% |
| `webhook_woocommerce` | 103.81 | 125.55 | 124.73 | +21.74 ms | +20.94% |

Between Run 1 and Run 3, overall p95 shifted by +31.4% without any application change. The cause was not investigated. CI runners share CPU and disk, so their variance is not expected to be lower. A 25% relative tolerance against a single baseline fails due to noise. Therefore, the relative comparison in CI uses `--tolerance 100`, while the absolute thresholds in each k6 script (p95 < 600 ms, error rate < 2%) act as the hard gate.

---

## 4. Performance Regression Gate

The regression gate script (`scripts/compare.py`) compares the current run summary against `baseline.json` using the Python standard library.

### Gate Rules:
1. **Latency Gate:** If the p95 of any endpoint increases by more than `--tolerance` percent (default 25%, CI uses `--tolerance 100`), the script exits with code 1.
2. **Reliability Gate:** If `http_req_failed` increases above the baseline rate, the script exits with code 1.
3. **Markdown Output:** Emits a table for step summaries.

#### Example Output (`scripts/compare.py results/load-summary-1.json baseline.json --tolerance 100`):

```markdown
### Performance Regression Gate Comparison

#### Response Time (p95)

| Metric / Endpoint | Baseline p95 (ms) | Current p95 (ms) | Delta (%) | Threshold | Status |
|---|---:|---:|---:|---:|:---:|
| `http_req_duration` (overall) | 177.36 | 138.19 | -22.09% | ≤ +100.0% | PASS |
| `admin_orders` | 437.74 | 342.44 | -21.77% | ≤ +100.0% | PASS |
| `webhook_shopify` | 116.90 | 100.33 | -14.18% | ≤ +100.0% | PASS |
| `webhook_woocommerce` | 125.55 | 103.81 | -17.32% | ≤ +100.0% | PASS |

#### Reliability / Error Rate

| Metric | Baseline Rate | Current Rate | Delta | Threshold | Status |
|---|---:|---:|---:|---:|:---:|
| `http_req_failed` | 0.00% | 0.00% | +0.00% | ≤ baseline | PASS |

#### Overall Gate Status

**Verdict:** ✅ PASSED
```

---

## 5. Historical Trend Tracking

`scripts/trend.py` scans a directory of run folders, reads `load-summary.json` from each, and outputs a table ordered by most recent run first:

```markdown
### Historical Performance Trend

| Run / Artifact | Total Reqs | Error Rate | Overall p95 | WooCommerce p95 | Shopify p95 | Admin Orders p95 | Status |
|---|---:|---:|---:|---:|---:|---:|:---:|
| `run-3` | 1492 | 0.00% | 181.62 ms | 124.73 ms | 115.77 ms | 346.16 ms | ✅ PASS |
| `run-2` | 1513 | 0.00% | 177.36 ms | 125.55 ms | 116.90 ms | 437.74 ms | ✅ PASS |
| `run-1` | 1499 | 0.00% | 138.19 ms | 103.81 ms | 100.33 ms | 342.44 ms | ✅ PASS |
```

---

## 6. SUT Findings and Defect Isolation

Concurrency issues identified during testing are detailed in [`docs/FINDINGS.md`](docs/FINDINGS.md):

- **FINDING-001:** Simultaneous deliveries of the same order cause a race condition between duplicate lookup and MongoDB insert, resulting in an unhandled `DuplicateKeyError` and HTTP 500. Sequential redeliveries respond with HTTP 200 ignored, and the MongoDB unique index prevents duplicate order records.

---

## 7. Known Limits

1. **Single-Host Loopback:** Tests run on a single host where k6, Docker, FastAPI, MongoDB, and Mailpit share CPU and memory bandwidth. Network latency does not reflect WAN transit.
2. **PBKDF2 Password Hashing:** `/admin/login` uses PBKDF2 with 600,000 iterations in production mode. Virtual users reuse session cookies after login to avoid dominating test execution with CPU key derivation.
3. **Local vs CI Differences:** GitHub Actions runners have different CPU and disk characteristics than local hardware. Regeneration of the baseline via `update_baseline` aligns comparisons with runner performance.

---

## 8. How to Run Locally

### 1. Start SUT Stack
```powershell
docker compose -f docker-compose.perf.yml up -d --build --wait
```

### 2. Run k6 Scenarios
```powershell
# Smoke Test
docker run --rm -v "${PWD}/k6:/k6" -v "${PWD}/results:/results" -e BASE_URL=http://host.docker.internal:8000 grafana/k6:2.3.0 run /k6/smoke.js --summary-export=/results/smoke-summary.json

# Load Test (Runs 1, 2, 3)
docker run --rm -v "${PWD}/k6:/k6" -v "${PWD}/results:/results" -e BASE_URL=http://host.docker.internal:8000 grafana/k6:2.3.0 run /k6/load.js --summary-export=/results/load-summary.json

# Spike Test
docker run --rm -v "${PWD}/k6:/k6" -v "${PWD}/results:/results" -e BASE_URL=http://host.docker.internal:8000 grafana/k6:2.3.0 run /k6/spike.js --summary-export=/results/spike-summary.json

# Negative Security Test
docker run --rm -v "${PWD}/k6:/k6" -v "${PWD}/results:/results" -e BASE_URL=http://host.docker.internal:8000 grafana/k6:2.3.0 run /k6/negative.js --summary-export=/results/negative-summary.json
```

### 3. Run Python Unit Tests & Linting
```powershell
uv venv .venv
uv pip install pytest ruff
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m ruff check scripts tests
```

### 4. Evaluate Regression Gate
```powershell
.venv\Scripts\python.exe scripts\compare.py results\load-summary-1.json baseline.json --tolerance 100
```

### 5. Compile Historical Trend
```powershell
.venv\Scripts\python.exe scripts\trend.py past_summaries
```

### 6. Tear Down Stack
```powershell
docker compose -f docker-compose.perf.yml down -v
```
