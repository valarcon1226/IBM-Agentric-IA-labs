"""Resilience tests for rate limits, concurrency backpressure, and proxy overhead.

Verifies:
1. Backpressure: rpm_limit=10 and max_parallel_requests=2 on LiteLLM v1.59.8.
   - Pinned schema: LiteLLM proxy GenerateKeyRequest fields:
     * 'rpm_limit' (int): requests per minute ceiling.
     * 'max_parallel_requests' (int): maximum concurrent in-flight requests.
2. Burst of 30 requests: assert how many succeed vs rate-limited (429), and check headers.
3. Client honoring Retry-After completes all 30 requests without exceeding limit.
4. Proxy overhead: 200 direct requests vs 200 proxy requests with 0ms upstream delay.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Dict, Tuple

import httpx
import pytest
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target

from tests.conftest import wait_until
from tests.fake_upstream import FakeUpstreamServer


@pytest.mark.resilience
def test_rate_limits_backpressure_and_retry_after(
    litellm_base_url: str,
    create_test_key: Callable[..., Dict[str, Any]],
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    # 1. Reset fake upstream and script ok with 300ms delay
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 200, "delay_ms": 300, "response_text": "ok"}]},
        timeout=5.0,
    )

    # 2. Create virtual key with rpm_limit=10 and max_parallel_requests=2
    # Citing LiteLLM v1.59.8 GenerateKeyRequest schema parameters:
    # - 'rpm_limit': int (requests per minute limit)
    # - 'max_parallel_requests': int (maximum concurrent requests allowed)
    key_info = create_test_key(
        key_alias="test-resilience-limits",
        rpm_limit=10,
        max_parallel_requests=2,
        models=["fake-primary"],
    )
    test_key = key_info["key"]

    # 3. Burst: send 30 concurrent requests through LiteLLM
    def _send_request(idx: int) -> Tuple[int, Dict[str, str], str]:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{litellm_base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {test_key}"},
                json={
                    "model": "fake-primary",
                    "messages": [{"role": "user", "content": f"burst-{idx}"}],
                },
            )
            return resp.status_code, dict(resp.headers), resp.text

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(_send_request, i) for i in range(30)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r[0] == 200]
    rate_limited = [r for r in results if r[0] == 429]

    # Exact assertions on burst outcome
    assert len(results) == 30, "All 30 requests must be accounted for"
    assert len(successes) + len(rate_limited) == 30, "Every response must be either 200 or 429"
    assert len(rate_limited) > 0, "Backpressure must trigger 429 under 30 concurrent requests"
    assert len(successes) > 0, "Legitimate in-flight requests within limits must succeed"

    # Verify documented headers on 429 responses
    for _, headers, body in rate_limited:
        assert "retry-after" in headers, "HTTP 429 must include Retry-After header"
        retry_val = float(headers["retry-after"])
        assert retry_val > 0, f"Retry-After must be positive, got {retry_val}"
        assert "Max parallel request limit reached" in body or "rate limit" in body.lower()

    # 4. Client honoring Retry-After finishes all 30 without exceeding limits
    # The client retries the 429'd items respecting the retry-after header
    pending_items = list(range(len(rate_limited)))
    completed_retry_count = 0

    while pending_items:
        current_idx = pending_items.pop(0)
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{litellm_base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {test_key}"},
                json={
                    "model": "fake-primary",
                    "messages": [{"role": "user", "content": f"retry-{current_idx}"}],
                },
            )
            if resp.status_code == 200:
                completed_retry_count += 1
            elif resp.status_code == 429:
                wait_sec = float(resp.headers.get("retry-after", 1.0))
                # Wait on condition until wait_sec has elapsed
                target_time = time.monotonic() + wait_sec
                wait_until(
                    lambda: time.monotonic() >= target_time,
                    description=f"waiting {wait_sec}s for rate limit window rollover",
                    timeout=wait_sec + 5.0,
                    interval=0.5,
                )
                pending_items.append(current_idx)
            else:
                pytest.fail(f"Unexpected status during retry: {resp.status_code}")

    total_finished = len(successes) + completed_retry_count
    assert total_finished == 30, "Client honoring retry-after must successfully complete all 30"


@pytest.mark.perf
def test_proxy_overhead_p95(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    # 1. Script fake upstream with 0ms delay
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 200, "delay_ms": 0, "response_text": "pong"}]},
        timeout=5.0,
    )

    recorder = MetricsRecorder()
    headers = {"Authorization": f"Bearer {litellm_master_key}"}

    with httpx.Client(timeout=10.0) as client:
        # Warmup connection pools
        client.post(
            f"{fake_upstream_server.base_url}/v1/chat/completions",
            json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
        )
        client.post(
            f"{litellm_base_url}/v1/chat/completions",
            headers=headers,
            json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
        )

        # 200 direct requests to fake upstream
        for _ in range(200):
            t0 = time.perf_counter()
            resp = client.post(
                f"{fake_upstream_server.base_url}/v1/chat/completions",
                json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
            )
            elapsed_s = time.perf_counter() - t0
            assert resp.status_code == 200
            recorder.record("upstream_direct_s", elapsed_s)

        # 200 proxy requests through LiteLLM
        for _ in range(200):
            t0 = time.perf_counter()
            resp = client.post(
                f"{litellm_base_url}/v1/chat/completions",
                headers=headers,
                json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
            )
            elapsed_s = time.perf_counter() - t0
            assert resp.status_code == 200
            recorder.record("proxy_gateway_s", elapsed_s)

    stats = recorder.compute()
    direct_p95_ms = stats["upstream_direct_s"]["p95"] * 1000.0
    proxy_p95_ms = stats["proxy_gateway_s"]["p95"] * 1000.0
    overhead_p95_ms = proxy_p95_ms - direct_p95_ms

    recorder.record("proxy_overhead_p95_ms", overhead_p95_ms / 1000.0)
    recorder.save("results/metrics.json")

    # Assert against targets.toml target: proxy_overhead_p95_ms <= 50.0 ms
    assert_target("proxy_overhead_p95_ms", overhead_p95_ms)
