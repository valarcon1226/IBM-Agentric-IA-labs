# Findings — LLM Platform & Gateway Reliability (Project 38)

This document tracks defects, deviations, and behavioral limitations identified in the System Under Test (LiteLLM proxy `main-v1.59.8` and Open WebUI `0.5.18`).

---

## FINDING-001: Retry-After Is Applied Per Deployment, So a Provider Quota Shared by Several Deployments Keeps Being Hit (By Design)

- **Component:** LiteLLM Proxy Router (`litellm/router.py:async_function_with_retries` and `_time_to_sleep_before_retry`)
- **SUT Version:** `ghcr.io/berriai/litellm:main-v1.59.8`
- **Severity:** Low (documented LiteLLM design; an operational risk when several deployments share one provider quota)
- **Target / Expectation:** When an upstream LLM provider returns HTTP 429 with `Retry-After: 2`, the gateway must pause for at least 2.0 seconds before dispatching the retry attempt.
- **Measured Result:** Retry attempt dispatched after **0.02 seconds** ($\Delta t < 0.1\text{ s} \ll 2.0\text{ s}$).
- **Status:** By design in LiteLLM. The test stays `xfail(strict=True, raises=AssertionError, reason="FINDING-001")` to pin the behaviour for the shared-quota case.

### Reproduction Steps
1. Deploy LiteLLM proxy with multiple deployments configured under model group `fake-primary` (`fake-gpt-primary-1`, `fake-gpt-primary-2`, `fake-gpt-primary-3`) and fallback `fake-fallback`.
2. Script the upstream test double (`tests/fake_upstream.py`) to return HTTP 429 with header `Retry-After: 2` on the first attempt, followed by HTTP 200 on the second attempt.
3. Submit a chat completion request to `http://127.0.0.1:4000/v1/chat/completions` for model `fake-primary`.
4. Inspect the timestamps in the fake upstream attempt log:
   `wait_time = attempts[1]["timestamp"] - attempts[0]["timestamp"]`.

### Expected Result
LiteLLM router parses the `Retry-After: 2` header, pauses for at least 2.0 seconds (`wait_time >= 2.0`), and only then submits attempt 2 to the upstream.

### Actual Result
In `litellm/router.py`, `_time_to_sleep_before_retry` returns `0` whenever `len(healthy_deployments) > 0`:
```python
elif (
    healthy_deployments is not None
    and isinstance(healthy_deployments, list)
    and len(healthy_deployments) > 0
):
    return 0
```
Because `fake-gpt-primary-2` is available in the model group, LiteLLM ignores the upstream's rate limit backoff signal and immediately hammers the second deployment within 20 milliseconds (`wait_time = 0.02s`). Furthermore, if only a single deployment exists, `should_retry_this_error` raises `RateLimitError` immediately upon cooldown without performing any retry.

### Why this is a trade-off and not a defect
The router does this on purpose. Its docstring in `litellm/router.py` (`_time_to_sleep_before_retry`, v1.59.8) says: "It should instantly retry only when: 1. there are healthy deployments in the same model group 2. there are fallbacks for the completion call".

In this reproduction the three deployments of `fake-primary` point to the same fake upstream. That models several keys or regions that draw on one provider quota: an instant retry on another deployment hits the same limit again. When the deployments are independent, the instant retry is the intended behaviour.

Not covered yet: a model group with a single deployment, where the `Retry-After` header should be honoured.

### Evidence
Attempt log recorded by `tests/fake_upstream.py`:
```json
[
  {
    "attempt": 1,
    "model": "fake-gpt-primary-1",
    "response_status": 429,
    "timestamp": 1792614666.95,
    "behavior_applied": {"status": 429, "retry_after": 2}
  },
  {
    "attempt": 2,
    "model": "fake-gpt-primary-2",
    "response_status": 200,
    "timestamp": 1792614666.97,
    "behavior_applied": {"status": 200}
  }
]
```
Measured interval: $1792614666.97 - 1792614666.95 = 0.02\text{ s}$ (AssertionError: `0.02 < 2.0`).

---

## FINDING-002: Premature Stream Cut Disguised as Complete Response Across Gateway, API and Web UI

- **Component:** LiteLLM Proxy Stream Processing & Open WebUI (`main-v1.59.8` / `0.5.18`)
- **SUT Version:** LiteLLM `main-v1.59.8`, Open WebUI `0.5.18`
- **Severity:** High (Silent Data Truncation / False Completion)
- **Target / Expectation:** A cut stream mid-response (e.g. 5 chunks without `finish_reason` or `[DONE]`) must never be reported as a complete answer. Downstream clients (OpenAI SDK, Open WebUI API, and Web UI) must observe an error, missing `finish_reason`, or an explicit failure/retry banner.
- **Measured Result:** LiteLLM intercepts premature upstream socket disconnection and synthesizes a closing chunk containing `finish_reason: "stop"` followed by `data: [DONE]`. This causes Open WebUI API to treat the response as successful, and Open WebUI's web interface renders the truncated 5-word sentence as a complete, valid assistant message with zero error banners or retry warnings.
- **Status:** SUT remains unpatched per measurement rules. Tests asserting that cut streams surface as errors/warnings are marked `xfail(strict=True, raises=AssertionError, reason="FINDING-002")`.

### Reproduction Steps
1. Configure upstream test double (`tests/fake_upstream.py`) with `cut_after_chunks: 5`.
2. Issue a streaming chat completion request to LiteLLM proxy (`http://127.0.0.1:4000/v1/chat/completions`) with `stream: true`.
3. Observe raw SSE events transmitted from LiteLLM to client:
   - Upstream transmits: 5 chunks with `finish_reason: null`, then severs TCP connection via socket shutdown.
   - LiteLLM forwards: 5 data chunks, then generates a 6th chunk:
     `{"choices":[{"delta":{},"finish_reason":"stop","index":0}]}`
     followed by `data: [DONE]`.
4. Issue prompt through Open WebUI chat UI via Playwright in Microsoft Edge.
5. Inspect rendered DOM:
   - Message container displays partial text: `"One two three four five"`.
   - Alert count: 0 (no `role='alert'`, no red badges, no retry prompts).
   - Message status is marked final.

### Evidence
Playwright Edge DOM inspection output:
```
Sent prompt in Open WebUI. Waiting 6 seconds for response rendering...
--- FULL BODY TEXT EXCERPT ---
>> One two three four five
Error/Warning elements count: 0
Assistant message containers: 3
Msg container 1: 'fake-primary\n\nOne two three four five'
Msg container 2: 'One two three four five'
```
The user sees an unfinished thought presented as the complete, final answer from the AI platform.

---

## FINDING-003: In-Memory Race Condition in LiteLLM Spend Batch Tracking Causes Dropped Spend Updates

- **Component:** LiteLLM Proxy Spend Accounting (`litellm/proxy/utils.py:update_spend` & `litellm/proxy/proxy_server.py:1033`)
- **SUT Version:** `ghcr.io/berriai/litellm:main-v1.59.8`
- **Severity:** Medium (Financial Accounting / Inaccurate Spend Under Rapid Concurrency)
- **Target / Expectation:** Gateway tracks spend per key matching token prices within $\le \pm 1.0\%$ (`targets.toml: spend_accuracy_tolerance_pct = 1.0`).
- **Measured Result:** When requests overlap with database batch flushes (or when `proxy_batch_write_at` is set below 4 seconds), LiteLLM's in-memory transaction buffer drops 2% to 4% of request spend updates.
- **Status:** Mitigated via configuration (`proxy_batch_write_at: 6`). Root cause isolated in SUT source code.

### Root Cause Analysis
1. In `litellm/proxy/proxy_server.py:1033`, completion handlers update in-memory spend by directly mutating a shared dictionary on the Prisma client:
   ```python
   prisma_client.key_list_transactons[hashed_token] = (
       response_cost + prisma_client.key_list_transactons.get(hashed_token, 0)
   )
   ```
2. Concurrently, the scheduled background job `update_spend` (`litellm/proxy/utils.py:2636-2641`) iterates over the dictionary items and flushes them to PostgreSQL inside an async transaction batch:
   ```python
   async with transaction.batch_() as batcher:
       for token, response_cost in prisma_client.key_list_transactons.items():
           batcher.litellm_verificationtoken.update_many(
               where={"token": token},
               data={"spend": {"increment": response_cost}},
           )
   prisma_client.key_list_transactons = {}
   ```
3. Because `prisma_client.key_list_transactons` is not locked or swapped atomically, any request completing during the async database transaction adds its spend to `key_list_transactons`, only for line 2641 to blindly overwrite `prisma_client.key_list_transactons = {}`, discarding the newly accrued spend.
4. In addition, `proxy_server.py:3179` calculates the APScheduler interval as:
   `random.randint(proxy_batch_write_at - 3, proxy_batch_write_at + 3)`
   If `proxy_batch_write_at < 4`, the lower bound becomes zero or negative (e.g. `1 - 3 = -2`), causing APScheduler to exhibit erratic execution schedules.

---

## FINDING-004: Every Chunk Retrieved From an Attached Collection Gets the Same Source Id, So an Answer Cannot Cite a Document

- **Component:** Open WebUI chat middleware (`backend/open_webui/utils/middleware.py:801-804`)
- **SUT Version:** `ghcr.io/open-webui/open-webui:0.5.18`
- **Severity:** Medium (no per-document attribution for answers over a knowledge collection)
- **Target / Expectation:** The RAG prompt template asks the model for inline citations in the format `[source_id]`. The evaluation protocol (`docs/EVALS.md`, section 3.5) expects every citation to point to a corpus file.
- **Measured Result:** With the `k8s-concepts` collection attached, the five retrieved chunks reach the model as `<source_id>0</source_id>`, whatever file each one comes from. In the dev and test runs every citation that carries an id carries `0`. A few answers write the placeholder itself, `[source_id]` or `[source_id:0]`.
- **Status:** Open in 0.5.18. The eval runner maps `[0]` to the set of documents retrieved from the collection. `docs/EVAL-RESULTS.md` explains what citation validity measures under that mapping.

### Root Cause
```python
for source_idx, source in enumerate(sources):
    if "document" in source:
        for doc_idx, doc_context in enumerate(source["document"]):
            context_string += f"<source><source_id>{source_idx}</source_id><source_context>{doc_context}</source_context></source>\n"
```
`sources` holds one entry per attached item, and a collection is one item. The id is the index of the item, not of the document.

### Later Versions
Read in the upstream source, not tested here: `v0.5.20` has the same loop, `v0.6.0` uses `source_idx + 1` and is still per attached item, and `v0.6.18` numbers the sources per document with a `citation_idx_map`.

### Evidence
`evals/dev_answers.jsonl` and `evals/baseline_answers.jsonl` record, for each answer, the documents the server attached under each source id (field `attached`). Every record has a single id. Example, `GOLD-002`: the id `0` covers chunks of `architecture/cloud-controller.md` and `architecture/_index.md`, and the answer cites `[0]`.

---

## FINDING-005: The API Reports the Sources of a RAG Answer Only in a Stream, and Only When the Attached Item Carries a Name

- **Component:** Open WebUI chat middleware (`backend/open_webui/utils/middleware.py:836-840` and its stream wrapper)
- **SUT Version:** `ghcr.io/open-webui/open-webui:0.5.18`
- **Severity:** Low (affects API clients, not the web UI)
- **Target / Expectation:** A client that calls `POST /api/chat/completions` with a collection attached can read which documents the answer used.
- **Measured Result:**

| Request | Sources in the response |
|---|---|
| `stream: false`, `files: [{"type": "collection", "id": "<id>"}]` | None. Keys returned: `id`, `created`, `model`, `object`, `system_fingerprint`, `choices`, `usage` |
| `stream: true`, same `files` | None. The first event is already a completion chunk |
| `stream: true`, `files: [{"type": "collection", "id": "<id>", "name": "k8s-concepts"}]` | First event is `{"sources": [...]}` with the chunks and their file names |

- **Status:** Open in 0.5.18. The eval runner streams the answer and sends the collection name.

### Root Cause
The middleware keeps only the sources whose attached item has a name, and hands them over as an event:
```python
sources = [source for source in sources if source.get("source", {}).get("name", "")]

if len(sources) > 0:
    events.append({"sources": sources})
```
The events are written by the stream wrapper. A non-streamed response does not include them.

---

## FINDING-006: The Vector Search Misses Nearer Chunks in About One Question in Five, and the Affected Questions Change With Every Restart

- **Component:** Open WebUI retrieval with its default vector store, Chroma (`POST /api/v1/retrieval/query/collection`; the chat pipeline runs the same query)
- **SUT Version:** `ghcr.io/open-webui/open-webui:0.5.18`
- **Severity:** High for answer quality (the passage with the answer is dropped without any error)
- **Target / Expectation:** The five chunks sent to the model are the five nearest to the question, and the same question returns the same chunks.
- **Measured Result:** over the 96 answerable test questions:

| Comparison | Result |
|---|---|
| Two consecutive k=5 queries in the same uptime | Same chunks in 96 of 96 |
| First five of a k=200 query, across two restarts | Same chunks in 96 of 96 |
| k=5 query against the first five of the k=200 query | Different in 18 and in 17 of 96, on two restarts. In every such case the wide query returned chunks at a smaller distance |
| k=5 query after a restart against the chunks logged during the eval run | Different in 9, 12 and 10 of 96, on three restarts |
| Chunks logged during the eval run against the first five of the k=200 query | Different in 17 of 96 |

- **Effect on the evaluation:** in 5 questions the run got no chunk of the gold document although the wide query ranks one in its top five. All 5 were refused. In the 79 questions where the run's chunks matched the wide query, key-fact correctness was 0.77 and the false refusal rate 0.06. In the other 17 they were 0.41 and 0.41. See `docs/EVAL-RESULTS.md`.
- **Status:** Open. The cause was not investigated: the index parameters of the vector store were not read.

### Example
`GOLD-081`, "What is an Indexed completion mode?". During the run the model received chunks of `services-networking/endpoint-slices.md`, `scheduling-eviction/scheduling-framework.md` and `cluster-administration/flow-control.md`, and refused. The wide query returns five chunks of `workloads/controllers/job.md`, the gold document, the nearest at distance 0.4475.

### Reproduction Steps
1. Bring the stack up and ingest the corpus (`scripts/ingest.py`).
2. Run `python -m scripts.retrieval_check --answers evals/baseline_answers.jsonl --out /tmp/check-1.json`.
3. Restart the stack with `docker compose stop` and `docker compose start`, and run step 2 again with another output file.
4. In each file compare `k5` with `wide5`, and compare the `k5` lists of the two files.

### Evidence
`evals/retrieval_check.json` holds the third measurement: for each question, the chunks logged during the run, the k=5 chunks, the first five of the k=200 query and their distances. The first two measurements were taken with the same queries during the analysis and are not committed.

---

## Operational Note: The Prompt Cache of the Ollama Model Runner Can Use All the Host Memory

This is about the Ollama service on the host (version 0.33.3), not about the pinned containers.

- **Observation:** During the RAG evaluation the runner process of the pinned model (`llama-server`) grew about 30 MB per request: 121 MB of anonymous memory over four requests. After a few hundred requests it held 8.3 GB between resident memory and swap, on a host with 7.6 GiB of RAM. Available memory fell below 600 MB and swap use reached 6.8 GB of 8 GB.
- **Likely cause:** Ollama starts `llama-server` without `--cache-ram`, and the help text of that binary gives the default host-memory prompt cache as 8192 MiB. This comes from the command line of the process and the help text. No memory profile was taken.
- **Mitigation used:** `ollama stop <model>` every 10 minutes during the test run, 27 times in 4 hours 53 minutes. The command waits for the request in flight and the next request loads the model again. No evaluation request failed, and available memory at each unload stayed between 0.4 GB and 2.3 GB.
- **Not tested:** limiting the cache with `LLAMA_ARG_CACHE_RAM` in the Ollama service, which needs a restart of a service shared with other workloads.
