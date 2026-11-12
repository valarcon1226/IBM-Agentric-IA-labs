# 38-llm-platform-evals · Internal Knowledge Assistant QA & Eval Platform

QA, resilience and evaluation suites for a self-hosted LLM platform:
- **LiteLLM Proxy** (pinned `ghcr.io/berriai/litellm:main-v1.59.8`) with PostgreSQL (`postgres:16.8-alpine3.21`) for virtual key management, budget tracking, spend auditing, rate-limiting, and model routing/fallback.
- **Ollama Engine** running directly on the homelab host as a systemd daemon (`127.0.0.1:11434`) serving pinned local model `qwen3:4b-instruct-2507-q4_K_M` (digest: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`).
- **Open WebUI** (pinned `ghcr.io/open-webui/open-webui:0.5.18`) providing document ingestion, vector retrieval, and RAG completion over the Kubernetes concepts corpus.
- **Test Double (Fake Upstream)** (`tests/fake_upstream.py`): stdlib Python HTTP server emulating OpenAI-compatible endpoints with deterministic fault injection (HTTP 429, 500, 400, deliberate latency, stream truncation). **Note: This component is strictly a test double and NOT part of the System Under Test (SUT).**

---

## Results

### RAG evaluation

A pre-registered protocol ([`docs/EVALS.md`](docs/EVALS.md)), 150 questions over 187 pages of the Kubernetes documentation, and three passes over the 120 test questions with a local 4B model. The assistant meets three of the five thresholds and misses two, so it does not pass the gate.

| Metric | Threshold | Test split | Verdict |
|---|---|---|---|
| Retrieval Hit@5 | ≥ 0.85 | 0.938 | Pass |
| Key-fact correctness | ≥ 0.75 | 0.708 | **Fail** |
| Refusal rate on unanswerable questions | ≥ 0.90 | 1.000 | Pass |
| False refusal rate | ≤ 0.10 | 0.125 | **Fail** |
| Citation validity | = 1.00 | 1.000 | Pass, with a limit |

The three passes scored identically and no request failed. A check made after the run traces most misses to retrieval: when the five retrieved chunks held every key fact, the model answered correctly 60 times out of 66. Details, decisions taken before the test run and limits are in [`docs/EVAL-RESULTS.md`](docs/EVAL-RESULTS.md).

### Findings

Six findings and one operational note in [`docs/FINDINGS.md`](docs/FINDINGS.md):

| Finding | Component | Summary |
|---|---|---|
| 001 | LiteLLM | Retries skip `Retry-After` when another deployment is healthy. By design, and a risk when deployments share one quota |
| 002 | LiteLLM, Open WebUI | A stream cut by the upstream is closed with `finish_reason: stop` and shown as a complete answer |
| 003 | LiteLLM | Spend updates are lost when a request finishes during the batch write |
| 004 | Open WebUI | Every chunk of an attached collection gets the same source id, so an answer cannot cite a document |
| 005 | Open WebUI | The API reports the sources of an answer only in a stream and only for a named item |
| 006 | Open WebUI | The vector search misses nearer chunks in about one question in five, and the affected questions change with every restart |

---

## Architecture & Homelab Host Networking

In accordance with homelab deployment constraints:
1. **Ollama Integration:** The Ollama server is managed by systemd on the host (`127.0.0.1:11434`) and is shared with other services on the same host. To allow LiteLLM and Open WebUI containers to communicate with host-bound loopback services without exposing Ollama publicly or changing systemd configs, containers run with `network_mode: host`.
2. **Port Mappings:**
   - PostgreSQL: `127.0.0.1:5432`
   - LiteLLM Proxy: `127.0.0.1:4000`
   - Open WebUI: `127.0.0.1:8088` (customized via `PORT=8088` to avoid collision with port 3000 which is occupied by Homepage)
   - Ollama: `127.0.0.1:11434`
   - Fake Upstream (Test Double): `127.0.0.1:8001`
3. **Resource Isolation:** Memory limits (`mem_limit`) are strictly assigned in `docker-compose.yml` to prevent starvation on the 7.6 GiB RAM host.

---

## Directory Structure

```text
38-llm-platform-evals/
├── docker-compose.yml          # Container stack (postgres, litellm, open-webui)
├── pyproject.toml              # Project dependencies and tool configurations
├── targets.toml                # Frozen performance, overhead, and quality targets
├── litellm/
│   └── config.yaml             # LiteLLM routing, model pricing, and fallback rules
├── evals/
│   ├── config.toml             # Pinned model digest, corpus commit, and eval parameters
│   ├── golden.jsonl            # Golden evaluation question set (dev & test splits)
│   ├── validate.py             # Pre-registration schema and path validator
│   ├── metrics.py              # Metric formulas of the protocol as pure functions
│   ├── run.py                  # Eval runner: asks every question through Open WebUI and scores it
│   ├── dev.json                # Dev-split run used to freeze the prompt (+ dev_answers.jsonl)
│   ├── baseline.json           # Test-split run, three passes (+ baseline_answers.jsonl)
│   └── retrieval_check.json    # Output of scripts/retrieval_check.py for that run
├── scripts/
│   ├── setup.py                # Virtual key generation and model reachability check
│   ├── corpus.py               # Downloads and converts the pinned Kubernetes docs; its ingestion step feeds the partial-failure check
│   ├── ingest.py               # Loads the converted corpus into the `k8s-concepts` collection for the RAG eval
│   └── retrieval_check.py      # Post-hoc check: what the search returned against a much wider search
├── tests/
│   ├── fake_upstream.py        # OpenAI-compatible scripted fault test double
│   ├── test_fake_upstream.py   # Unit tests for test double behavior and attempt logging
│   ├── evals/                  # Golden-set validation, metric and runner unit tests (no network)
│   ├── api/                    # Cost auditing, pagination, and API contract tests
│   ├── resilience/             # Rate limits (RPM/concurrency), retries, and cut stream handling
│   └── migration/              # LiteLLM N-1 to N schema and state migration tests
└── docs/
    ├── HARDWARE.md             # Homelab hardware specifications (CPU, RAM, GPU)
    ├── RISK-ANALYSIS.md        # L x I risk matrix and mitigation strategies
    ├── EVALS.md                # Frozen RAG evaluation protocol and metric formulas
    ├── EVAL-RESULTS.md         # RAG evaluation results, decisions taken before the test run, and limits
    └── FINDINGS.md             # Defect tracking and SUT deviation logs
```

---

## Execution Instructions

### 1. Environment & Stack Startup (Homelab)

In the homelab host (`ssh <user>@<homelab-host>` inside `~/qa/38-llm-platform-evals`):

```bash
# 1. Export master key (never committed to repo or .env)
export LITELLM_MASTER_KEY="<your-master-key>"

# 2. Start the isolated container stack (postgres, litellm, open-webui)
docker compose up -d --wait

# 3. Verify health and initialize key / model reachability
uv run python scripts/setup.py
```

### 2. Running Test Suites

Run each suite on a fresh stack (`docker compose down -v && docker compose up -d --wait && uv run python scripts/setup.py`):

```bash
# Unit & Evals validation suite
uv run pytest tests/test_fake_upstream.py tests/evals -v

# API contracts suite (cost accounting and pagination)
uv run pytest tests/api -v

# Resilience suite 1: Rate limits, concurrency and proxy overhead
uv run pytest tests/resilience/test_limits.py -v

# Resilience suite 2: Retries, 500 fallback and 429 backoff
uv run pytest tests/resilience/test_retries.py -v

# Resilience suite 3: Cut streaming detection (SDK & Open WebUI API)
uv run pytest tests/resilience/test_stream_cut.py -v

# Migration suite: LiteLLM N-1 (v1.58.0) to N (v1.59.8) schema upgrade
uv run pytest -m migration -v
```

### 3. RAG Evaluation (Homelab)

The protocol is in [`docs/EVALS.md`](docs/EVALS.md) and the results in [`docs/EVAL-RESULTS.md`](docs/EVAL-RESULTS.md).

```bash
# Load the 187 corpus files into the Open WebUI collection `k8s-concepts`.
# About 14 minutes: the embeddings run on CPU. It also sets k=5 and turns query rewriting off.
uv run python scripts/ingest.py

# Dev split, one pass over 30 questions. The only split used to adjust the prompt.
uv run python -m evals.run --split dev --out results/dev.json --answers results/dev_answers.jsonl

# Test split, three passes over 120 questions, compared with the committed baseline.
# The command exits with 1 when a metric falls more than 0.03 below the baseline.
uv run python -m evals.run --split test --baseline evals/baseline.json
```

A test run takes about five hours on the 4 GB GPU. It needs the real stack and the GPU, so it runs on the homelab and not in GitHub Actions. CI runs the unit tests of the metrics, the runner and the golden set.

### 4. Edge UI Resilience Test via SSH Tunnel (Laptop)

The Layer 3 UI test requires Microsoft Edge and Playwright, run from the laptop via an SSH tunnel to the homelab:

```bash
# On Laptop (Terminal 1 - Establish SSH tunnel to Open WebUI and LiteLLM):
ssh -N -L 8088:127.0.0.1:8088 -L 4000:127.0.0.1:4000 <user>@<homelab-host>

# On Laptop (Terminal 2 - Execute Layer 3 Playwright Edge test):
export LITELLM_MASTER_KEY="<your-master-key>"
export OPENWEBUI_BASE_URL="http://127.0.0.1:8088"
export LITELLM_BASE_URL="http://127.0.0.1:4000"
uv run pytest tests/resilience/test_stream_cut.py -k test_stream_cut_layer3_openwebui_edge_ui -v
```

### 5. Code Quality & Formatting Checks

```bash
uv run ruff check .
uv run mypy tests scripts evals
```

### 6. Teardown

```bash
# -v also deletes the ingested collection; leave it out to keep the corpus loaded
docker compose down -v
```
