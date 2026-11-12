# Risk Analysis — LLM Platform & Internal Knowledge Assistant

Comprehensive Likelihood $\times$ Impact ($L \times I$) risk assessment for the enterprise LLM gateway and RAG evaluation platform.

## 1. Risk Evaluation Scale

- **Likelihood ($L$):** 1 (Rare), 2 (Unlikely), 3 (Moderate), 4 (Likely), 5 (Almost Certain)
- **Impact ($I$):** 1 (Negligible), 2 (Minor), 3 (Moderate), 4 (Major), 5 (Catastrophic)
- **Risk Score ($R = L \times I$):**
  - **1 – 6:** Low Risk (Monitor)
  - **7 – 14:** Medium Risk (Mitigate through automated testing and telemetry)
  - **15 – 25:** High Risk (Critical barrier; mandatory PR gating and automated circuit breakers)

---

## 2. Risk Matrix

| Risk ID | Risk Description | $L$ | $I$ | $R$ | Primary Mitigation & Automated Test |
|---|---|:---:|:---:|:---:|---|
| **RSK-01** | **Runaway Cost & Budget Depletion:** Looping internal agents or leaked API keys submit unbounded high-token requests, draining model budgets rapidly. | 4 | 5 | **20** | Enforce per-key `max_budget` and token-spend tracking directly in LiteLLM Postgres backend. Verified in `tests/api/test_cost.py`. |
| **RSK-02** | **Upstream Provider Outage:** The primary LLM backend experiences degraded availability, network partitions, or repeated HTTP 5xx errors. | 4 | 4 | **16** | Configure automatic multi-model failover routing with strict timeouts and exponential backoff. Verified in `tests/resilience/test_retries.py`. |
| **RSK-03** | **Retry Storms & Gateway Saturation:** Multiple concurrent clients aggressively retry failed requests without honoring `Retry-After`, amplifying outage severity. | 4 | 4 | **16** | Strict rate limits (`rpm`, `max_parallel_requests`) returning HTTP 429 with `Retry-After`. Client retry backoff compliance verified in `tests/resilience/test_limits.py`. |
| **RSK-04** | **Truncated Answers Disguised as Success:** A broken SSE token stream abruptly drops connection; client UI renders the incomplete sentence as a complete final answer. | 3 | 4 | **12** | Inspect stream completion invariants across SDK, gateway proxy, and browser UI, ensuring cut streams produce visible errors. Verified in `tests/resilience/test_stream_cut.py`. |
| **RSK-05** | **Hallucinations & Factually Incorrect Answers:** Non-deterministic generation produces fabricated Kubernetes concepts or commands presented as factual truth. | 4 | 4 | **16** | Golden eval protocol enforcing regex-based key-fact checks on answerable questions with threshold $\ge 0.75$. Verified in `evals/run.py`. |
| **RSK-06** | **Missed Document Retrieval (RAG Recall Failure):** Semantic search fails to retrieve relevant concept files into context window, leading to answer degradation or false refusals. | 3 | 4 | **12** | Retrieval hit@5 benchmark with threshold $\ge 0.85$ over frozen test set of 120 questions. Verified in `evals/run.py`. |
| **RSK-07** | **Upgrade Data Loss & Broken Migrations:** Upgrading LiteLLM proxy between major or minor versions drops virtual keys, spend records, or corrupts schema tables. | 2 | 5 | **10** | Automated N-1 to N database migration test validating zero state discrepancies across all user keys and spend records. Verified in `tests/migration/test_upgrade.py`. |
| **RSK-08** | **Partial Ingestion Failure & Unindexed Documents:** Ingesting large document batches halts silently on unparseable/binary files, leaving knowledge base silently incomplete. | 3 | 3 | **9** | Batch ingestion pipeline that isolates corrupted documents, records explicit failure causes, and confirms 100% of valid files are indexed. Verified in `scripts/corpus.py`. |

---

## 3. Mitigation Architecture

1. **Gateway-Level Controls:**
   - LiteLLM proxy sits between client applications and downstream models (Ollama, cloud LLMs).
   - Enforces key-level rate limiting, concurrency quotas, and spend ledger persistence in PostgreSQL.
2. **Deterministic Evaluation Protocol:**
   - Pre-registration in `docs/EVALS.md` prevents tuning hyperparameters to the evaluation split.
   - Fixed temperature ($0.0$) and seed ($42$) with 3-run variance tracking ensure repeatable benchmarks.
3. **Resilience Test Doubles:**
   - Use of `tests/fake_upstream.py` enables exact deterministic simulation of HTTP 429, 500, socket cutoffs, and delay injection without incurring live LLM costs.
