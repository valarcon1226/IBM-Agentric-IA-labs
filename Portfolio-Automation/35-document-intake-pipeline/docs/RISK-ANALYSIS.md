# Risk Analysis: Document Intake Pipeline (Paperless-ngx)

This document formalizes the risk assessment for the Paperless-ngx document ingestion and processing architecture. Each functional area is evaluated on Likelihood ($L \in [1, 5]$) and Impact ($I \in [1, 5]$), producing a Risk Score ($R = L \times I$).

---

## 1. Risk Matrix

| Risk Level | Score ($L \times I$) | Action Required |
|---|---|---|
| **Critical** | $16 - 25$ | Mandatory automated gate in PR CI; rigorous chaos and fault testing. |
| **High** | $10 - 15$ | P1 regression test suite coverage and target assertion in `targets.toml`. |
| **Medium** | $5 - 9$ | Integration and nightly validation suite. |
| **Low** | $1 - 4$ | Monitored with diagnostic logging and baseline checks. |

---

## 2. Risk Assessment by Area

### 1. Upload (`/api/documents/post_document/`)
- **Failure Mode:** Concurrent HTTP multi-part bursts exhaust webserver memory, cause connection timeouts, or result in HTTP 500 crashes under resource constraints.
- **Likelihood ($L$):** 4 | **Impact ($I$):** 4 | **Risk Score ($R$):** **16 (Critical)**
- **Mitigation:**
  - Enforce `mem_limit: 2g` on the webserver container.
  - Implement client-side concurrency control (`asyncio.Semaphore(50)`).
  - Verify every HTTP upload returns an asynchronous task UUID immediately.
- **Verification:** `tests/resilience/test_burst.py` (REQ-ING-001).

### 2. The Queue (Redis Broker & Celery Distribution)
- **Failure Mode:** Redis broker disconnection or restarts leave tasks in zombie `PENDING` or `STARTED` states, leading to lost ingestion jobs or task starvation.
- **Likelihood ($L$):** 3 | **Impact ($I$):** 5 | **Risk Score ($R$):** **15 (High)**
- **Mitigation:**
  - Mediate Redis connections through Toxiproxy to test network severances.
  - Verify Celery worker auto-reconnect and task state reconciliation.
  - Assert zero dangling tasks remaining after fault clearing.
- **Verification:** `tests/resilience/test_faults.py` (REQ-ING-002).

### 3. The Consumer (Document Parser & Ingestion Worker)
- **Failure Mode:** Malformed, truncated, or password-protected PDFs trigger unhandled exceptions in `pdfminer`/PyMuPDF, locking the worker thread or leaving orphan files in `media/documents/originals`.
- **Likelihood ($L$):** 4 | **Impact ($I$):** 3 | **Risk Score ($R$):** **12 (High)**
- **Mitigation:**
  - Robust exception handling in the consumer pipeline capturing parsing syntax errors.
  - Ensure task failure records the explicit error message and purges uncommitted file fragments.
- **Verification:** `tests/api/test_partial.py` (REQ-ING-004, REQ-ING-006).

### 4. Duplicates (Checksum Deduplication & Client Retries)
- **Failure Mode:** Client retries following network glitches create duplicate document entries, contaminating document counts and corrupting financial ledgers.
- **Likelihood ($L$):** 4 | **Impact ($I$):** 4 | **Risk Score ($R$):** **16 (Critical)**
- **Mitigation:**
  - Compute SHA-256 checksum on document upload.
  - Enforce database uniqueness constraints and reject duplicate byte payloads.
  - Idempotent task completion acknowledging duplicate detection.
- **Verification:** `tests/resilience/test_faults.py` (REQ-ING-003).

### 5. Search (Whoosh Index & Query Consistency)
- **Failure Mode:** Search index drift during heavy asynchronous ingestion; queries fail to locate ingested documents, or paginated search returns duplicate/missing entries under score ties.
- **Likelihood ($L$):** 3 | **Impact ($I$):** 3 | **Risk Score ($R$):** **9 (Medium)**
- **Mitigation:**
  - Background index updater commits search documents reliably.
  - Test pagination with exact tie-breaking ordering on 300 documents.
  - Assert exact 120 matching unique items for targeted search queries.
- **Verification:** `tests/api/test_pagination.py` (REQ-ING-007, REQ-ING-008).

### 6. Bulk Edit (`/api/bulk_edit/`)
- **Failure Mode:** Bulk tag or metadata operations referencing deleted or non-existent document IDs crash with 500 Internal Server Error, leaving partial batch modifications in an inconsistent state.
- **Likelihood ($L$):** 3 | **Impact ($I$):** 4 | **Risk Score ($R$):** **12 (High)**
- **Mitigation:**
  - Document and assert exact API contract behavior when missing IDs are supplied.
  - Verify database transaction boundary prevents partial corruption.
- **Verification:** `tests/api/test_partial.py` (REQ-ING-005).

### 7. The Classifier (Automatic Document Type Classifier)
- **Failure Mode:** Machine learning classifier exhibits severe class imbalance bias, yielding low recall on critical document classes (e.g. utility bills or letters), or overfitting on synthetic artifacts.
- **Likelihood ($L$):** 4 | **Impact ($I$):** 3 | **Risk Score ($R$):** **12 (High)**
- **Mitigation:**
  - Pre-registered evaluation protocol (`docs/EVALS.md`) with stratified 500/100 train/test split.
  - Hard performance gates: Macro-F1 $\ge 0.90$ and minimum type recall $\ge 0.80$ across 3 random seeds.
  - Pure Python metrics calculation with zero evaluation leakage.
- **Verification:** `tests/eval/test_classifier.py` (REQ-ING-009).

### 8. Upgrade (Schema & Application Binary Migrations)
- **Failure Mode:** Migration from version N-1 to N corrupts custom fields, notes, document tags, or alters media archive files, without verified rollback path.
- **Likelihood ($L$):** 2 | **Impact ($I$):** 5 | **Risk Score ($R$):** **10 (High)**
- **Mitigation:**
  - Test upgrade between pinned distinct versions (2.14.6 $\rightarrow$ 2.14.7) on 500 real documents.
  - Assert zero byte differences on archive checksums and identical metadata counts.
  - Execute and verify full database snapshot rollback restoring N-1 fidelity.
- **Verification:** `tests/migration/test_upgrade.py` (REQ-ING-010).
