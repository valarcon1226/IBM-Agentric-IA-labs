# Findings — LLM Platform & Gateway Reliability (Project 38)

This document tracks defects, deviations, and behavioral limitations identified in the System Under Test (LiteLLM proxy `main-v1.59.8` and Open WebUI `0.5.18`).

---

## FINDING-001: LiteLLM Router Bypasses Upstream Retry-After Duration on 429 Errors

- **Component:** LiteLLM Proxy Router (`litellm/router.py:async_function_with_retries` and `_time_to_sleep_before_retry`)
- **SUT Version:** `ghcr.io/berriai/litellm:main-v1.59.8`
- **Severity:** Medium (Upstream Concurrency / Provider Compliance)
- **Target / Expectation:** When an upstream LLM provider returns HTTP 429 with `Retry-After: 2`, the gateway must pause for at least 2.0 seconds before dispatching the retry attempt.
- **Measured Result:** Retry attempt dispatched after **0.02 seconds** ($\Delta t < 0.1\text{ s} \ll 2.0\text{ s}$).
- **Status:** SUT remains unpatched per measurement rules. Test marked `xfail(strict=True, raises=AssertionError, reason="FINDING-001")`.

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


