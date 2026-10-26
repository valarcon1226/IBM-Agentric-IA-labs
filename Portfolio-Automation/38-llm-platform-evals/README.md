# 38-llm-platform-evals · Internal Knowledge Assistant QA & Eval Platform

This project implements an automated QA, resilience, and evaluation framework for an enterprise AI platform:
- **LiteLLM Proxy** (pinned `ghcr.io/berriai/litellm:main-v1.59.8`) with PostgreSQL (`postgres:16.8-alpine3.21`) for virtual key management, budget tracking, spend auditing, rate-limiting, and model routing/fallback.
- **Ollama Engine** running directly on the homelab host as a systemd daemon (`127.0.0.1:11434`) serving pinned local model `qwen3:4b-instruct-2507-q4_K_M` (digest: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`).
- **Open WebUI** (pinned `ghcr.io/open-webui/open-webui:0.5.18`) providing document ingestion, vector retrieval, and RAG completion over the Kubernetes concepts corpus.
- **Test Double (Fake Upstream)** (`tests/fake_upstream.py`): stdlib Python HTTP server emulating OpenAI-compatible endpoints with deterministic fault injection (HTTP 429, 500, 400, deliberate latency, stream truncation). **Note: This component is strictly a test double and NOT part of the System Under Test (SUT).**

---

## Architecture & Homelab Host Networking

In accordance with homelab deployment constraints:
1. **Ollama Integration:** The Ollama server is managed by systemd on the host (`127.0.0.1:11434`) and is shared with production services (e.g. `jobHunter`). To allow LiteLLM and Open WebUI containers to communicate with host-bound loopback services without exposing Ollama publicly or changing systemd configs, containers run with `network_mode: host`.
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
│   └── validate.py             # Pre-registration schema and path validator
├── scripts/
│   ├── setup.py                # Virtual key generation and model reachability check
│   └── corpus.py               # Kubernetes documentation fetcher and ingestion pipeline
├── tests/
│   ├── fake_upstream.py        # OpenAI-compatible scripted fault test double
│   ├── test_fake_upstream.py   # Unit tests for test double behavior and attempt logging
│   ├── api/                    # Cost auditing, pagination, and API contract tests
│   ├── resilience/             # Rate limits (RPM/concurrency), retries, and cut stream handling
│   └── migration/              # LiteLLM N-1 to N schema and state migration tests
└── docs/
    ├── HARDWARE.md             # Homelab hardware specifications (CPU, RAM, GPU)
    ├── RISK-ANALYSIS.md        # L x I risk matrix and mitigation strategies
    ├── EVALS.md                # Frozen RAG evaluation protocol and metric formulas
    └── FINDINGS.md             # Defect tracking and SUT deviation logs
```

---

## Execution Instructions

### 1. Environment & Stack Startup (Homelab)

In the homelab host (`ssh valentina@192.168.1.15` inside `~/qa/38-llm-platform-evals`):

```bash
# 1. Export master key (never committed to repo or .env)
export LITELLM_MASTER_KEY="sk-master-key-evals-homelab-1234"

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

### 3. Edge UI Resilience Test via SSH Tunnel (Laptop)

The Layer 3 UI test requires Microsoft Edge and Playwright, run from the laptop via an SSH tunnel to the homelab:

```bash
# On Laptop (Terminal 1 - Establish SSH tunnel to Open WebUI and LiteLLM):
ssh -N -L 8088:127.0.0.1:8088 -L 4000:127.0.0.1:4000 valentina@192.168.1.15

# On Laptop (Terminal 2 - Execute Layer 3 Playwright Edge test):
export LITELLM_MASTER_KEY="sk-master-key-evals-homelab-1234"
export OPENWEBUI_BASE_URL="http://127.0.0.1:8088"
export LITELLM_BASE_URL="http://127.0.0.1:4000"
uv run pytest tests/resilience/test_stream_cut.py -k test_stream_cut_layer3_openwebui_edge_ui -v
```

### 4. Code Quality & Formatting Checks

```bash
uv run ruff check .
uv run mypy tests scripts evals
```

### 5. Teardown

```bash
docker compose down -v
```
