# Document Intake Pipeline & Chaos Testing Suite (Paperless-ngx)

Comprehensive test harness, deterministic corpus generator, chaos resilience suite, and machine learning classifier benchmark for [Paperless-ngx](https://docs.paperless-ngx.com/).

---

## 1. Architecture Overview

The system under test is an enterprise document intake pipeline orchestrated with Docker Compose:

```
+-------------------------------------------------------------------------------+
|                                Host Machine                                   |
|                                                                               |
|  +-------------------------+      HTTP / API      +-----------------------+   |
|  |   Pytest & Locust       | -------------------> |  Paperless Webserver  |   |
|  |   Playwright Tests      | (127.0.0.1:8000)     |  (Gunicorn + Django)  |   |
|  +-------------------------+                      +-----------------------+   |
|                                                               |               |
|                                                   Celery Tasks| via Toxiproxy |
|                                                               v               |
|  +-------------------------+     Toxiproxy API    +-----------------------+   |
|  |    Chaos / Fault        | -------------------> |       Toxiproxy       |   |
|  |    Injection Tests      | (127.0.0.1:8474)     |  ghcr.io/shopify/...  |   |
|  +-------------------------+                      +-----------------------+   |
|                                                               |               |
|                                                        Proxied| Redis Traffic |
|                                                               v               |
|  +-------------------------+                      +-----------------------+   |
|  |       PostgreSQL        | <------------------- |         Redis         |   |
|  |    postgres:16.8-alpine |                      |      7.4.2-alpine     |   |
|  |    (127.0.0.1:5433)     |                      |    (127.0.0.1:6378)   |   |
|  +-------------------------+                      +-----------------------+   |
+-------------------------------------------------------------------------------+
```

### Components & Pinned Versions
- **Paperless-ngx**: `ghcr.io/paperless-ngx/paperless-ngx:2.14.7` (Current / N), `2.14.6` (N-1 for migration upgrade testing). Memory limit: `2 GB`.
- **PostgreSQL**: `postgres:16.8-alpine3.21` (Host port `5433` to prevent collision with default PostgreSQL installations). Memory limit: `512 MB`.
- **Redis**: `redis:7.4.2-alpine` (Host port `6378`). Memory limit: `256 MB`.
- **Toxiproxy**: `ghcr.io/shopify/toxiproxy:2.11.0` (Host ports `8474` HTTP API, `6379` Redis proxy). Memory limit: `128 MB`.

---

## 2. Prerequisites & Setup

### Requirements
- Docker & Docker Compose v2.20+
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) package manager

### Installation & Stack Bootstrap

```bash
# 1. Install dependencies and virtualenv
uv sync

# 2. Boot Docker Compose stack in detached mode
docker compose up -d --wait

# 3. Initialize admin user, verify API connectivity, and obtain auth token
uv run python scripts/setup.py
```

---

## 3. Deterministic Corpus Generator

The test corpus consists of 600 synthetic documents generated with pinned PDF metadata timestamps (`2026-01-01T00:00:00Z`) to ensure 100% byte-reproducibility across machines and architectures.

- **5 Document Types**: `invoice`, `purchase_order`, `bank_statement`, `utility_bill`, `letter`.
- **12 Global Correspondents**: Telecom, energy, utilities, banks, cloud infrastructure providers.
- **Controlled Error Ratios**:
  - Exactly **3% corrupt PDFs** (18 files truncated at header).
  - Exactly **2% duplicate PDFs** (12 byte-identical copies).
  - Exactly **95% valid ingestible PDFs** (570 files).

```bash
# Regenerate corpus (deterministic seed 42)
uv run python corpus/generate.py --seed 42 --count 600

# Verify determinism and error ratios via pytest
uv run pytest tests/test_corpus.py -v
```

---

## 4. Test Suite Execution

The test suite covers performance, chaos resilience, API contract edge cases, database migration fidelity, machine learning classification quality, and UI end-to-end flows.

### Running Individual Test Modules

```bash
# Burst Ingestion & Accounting (500 concurrent documents, Semaphore(50))
uv run pytest tests/resilience/test_burst.py -v -s

# Chaos & Fault Injection (Redis restart, Toxiproxy connection drop, retry idempotency)
uv run pytest tests/resilience/test_faults.py -v -s

# Partial Failures & API Validation (corrupt PDF, non-existent IDs in bulk edit, encrypted PDF)
uv run pytest tests/api/test_partial.py -v -s

# Pagination & Search Performance (300 tie pagination consistency, 50 latency samples p95)
uv run pytest tests/api/test_pagination.py -v -s

# Machine Learning Classifier Evaluation (stratified train/test split, Macro-F1 >= 0.90)
uv run pytest tests/eval/test_classifier.py -v -s -m eval

# Database Upgrade Migration N-1 to N (2.14.6 -> 2.14.7, 0 metadata/file loss, snapshot rollback)
uv run pytest tests/migration/test_upgrade.py -v -s -m migration

# Playwright End-to-End UI & Accessibility Audit (Edge/Firefox, inline axe-core)
uv run pytest tests/ui/test_document_flow.py -v -s
```

### Running the Entire Suite
```bash
uv run pytest -v
```

---

## 5. Measured Results & Target Baselines

All tests write benchmark and quality metrics into `results/metrics.json` and `results/evals.json`, validated against targets defined in `targets.toml`:

| Metric / Requirement | Target Baseline | Measured Result | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Ingestion Drain Time (500 docs)** | $\le 900.0$ s | **605.89 s** | PASSED | Concurrency semaphore = 50 |
| **Throughput Rate** | $\ge 40.0$ docs/min | **49.51 docs/min** | PASSED | P50 rate during burst drain |
| **Peak Webserver Memory** | $\le 1900.0$ MB | **1,270.78 MB** | PASSED | Well within 2 GB Docker limit |
| **Accounting Ratio** | $= 1.0$ (100%) | **1.0 (100%)** | PASSED | 500/500 documents accounted |
| **Listing Latency (p95)** | $\le 2000.0$ ms | **213.54 ms** | PASSED | 50 samples with 600 docs in DB |
| **Search Latency (p95)** | $\le 5000.0$ ms | **219.52 ms** | PASSED | 50 samples with Whoosh engine |
| **Pagination Consistency** | 0 duplicates / 0 missing | **0 duplicates / 0 missing** | PASSED | 300 docs with identical created timestamp |
| **Classifier Macro-F1 (3 seeds)** | $\ge 0.90$ | **1.0000** | PASSED | Evaluated on 1,800 docs across seeds 42, 101, 202 |
| **Classifier Min Recall** | $\ge 0.80$ | **1.0000** | PASSED | Evaluated on 1,800 docs across seeds 42, 101, 202 |
| **Migration Runtime (2.14.6 $\to$ 2.14.7)** | $\le 300.0$ s | **2.75 s** | PASSED | `manage.py migrate` on 600-document database |
| **Migration Data Fidelity** | 0 diffs / 0 file diffs | **0 metadata diffs / 0 file diffs** | PASSED | 600 docs, 3 tags, 5 types, 100 notes, 100 CF instances |
| **UI End-to-End Flow** | Edge upload, search, edit | **All 3 steps verified** | PASSED | Headless Microsoft Edge browser channel |
| **A11y Critical Violations** | $= 0$ | **6 violations** | XFAIL (SUT) | Pinned axe-core scan on `/documents`, see `FINDING-001` |

---

## 6. Documented Findings (SUT Defects)

Full technical analysis and reproductions are documented in [`docs/FINDINGS.md`](docs/FINDINGS.md):

- **[FINDING-001](docs/FINDINGS.md#finding-001-upstream-angular-spa-criticalserious-accessibility-violations)**: Paperless-ngx 2.14.7 Angular SPA exhibits 6 critical/serious accessibility violations on `/documents` (`aria-allowed-attr`, `aria-required-children`, `button-name`, `label`, `link-name`, `listitem`). Handled via `@pytest.mark.xfail(strict=True)`.
- **[FINDING-002](docs/FINDINGS.md#finding-002-encrypted-pdf-processing-skips-ocr-without-explicit-failure-status)**: Uploading an encrypted PDF results in a `SUCCESS` task status with extracted title and metadata, but OCR text extraction is silently skipped with an empty content field.

---

## 7. Engineering Quality Standards & Verification

- **Linting & Code Quality**: Enforced via `ruff check .` with zero warnings.
- **Type Safety**: Enforced via `mypy .` in strict mode with zero issues.
- **CI Workflow Validation**: Pinned commit SHAs in `.github/workflows/35-document-intake-pipeline.yml`, validated via `rhysd/actionlint:1.7.7` container.
- **Clean Teardown**:
  ```bash
  docker compose down -v
  ```

