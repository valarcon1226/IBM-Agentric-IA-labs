"""Resilience tests for LiteLLM retry and fallback policies.

Validates that retries and secondary fallbacks occur exactly as configured:
1. 500, 500, ok: LiteLLM retries up to num_retries times; client gets 200,
   attempt log shows 3 attempts.
2. 500 for every primary attempt: falls back to fallback-model, and response
   indicates fallback model answered.
3. 429 with Retry-After 2: gateway pauses at least 2 seconds before retrying
   (evaluated against FINDING-001).
4. 400: client gets 400; exactly 1 attempt is logged, with 0 retries.

Every assertion verifies the exact attempt count from the fake upstream's log,
not LiteLLM internal logs.
"""

from __future__ import annotations

import httpx
import pytest

from tests.fake_upstream import FakeUpstreamServer


@pytest.mark.resilience
def test_retry_500_recovery(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    # 1. Script upstream: 500, 500, ok
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {"status": 500, "error_message": "Transient failure 1"},
                {"status": 500, "error_message": "Transient failure 2"},
                {"status": 200, "response_text": "recovered-after-retries"},
            ]
        },
        timeout=5.0,
    )

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"{litellm_base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": "fake-primary",
                "messages": [{"role": "user", "content": "test 500 retry"}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["choices"][0]["message"]["content"] == "recovered-after-retries"

    # Assert exact attempt count from fake upstream attempt log
    attempts_resp = httpx.get(f"{fake_upstream_server.base_url}/control/attempts", timeout=5.0)
    attempts = attempts_resp.json()
    assert len(attempts) == 3, f"Expected exactly 3 upstream attempts, got {len(attempts)}"
    assert attempts[0]["response_status"] == 500
    assert attempts[1]["response_status"] == 500
    assert attempts[2]["response_status"] == 200


@pytest.mark.resilience
def test_retry_500_fallback(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    # 1. Script 500 for all primary attempts (1 initial + 2 retries = 3), then 200 for fallback
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {"status": 500, "error_message": "primary fail 1"},
                {"status": 500, "error_message": "primary fail 2"},
                {"status": 500, "error_message": "primary fail 3"},
                {"status": 200, "response_text": "answer from fallback model"},
            ]
        },
        timeout=5.0,
    )

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"{litellm_base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": "fake-primary",
                "messages": [{"role": "user", "content": "test fallback routing"}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["choices"][0]["message"]["content"] == "answer from fallback model"
        # Assert response explicitly reveals that the fallback model answered
        assert "fake-fallback" in body.get("model", "") or "fake-gpt-fallback" in body.get(
            "model", ""
        )

    # Check attempt log: 3 failed attempts on primary + 1 successful attempt on fallback
    attempts_resp = httpx.get(f"{fake_upstream_server.base_url}/control/attempts", timeout=5.0)
    attempts = attempts_resp.json()
    assert len(attempts) == 4, f"Expected exactly 4 upstream attempts, got {len(attempts)}"
    assert attempts[0]["response_status"] == 500
    assert attempts[1]["response_status"] == 500
    assert attempts[2]["response_status"] == 500
    assert attempts[3]["response_status"] == 200
    assert attempts[3]["model"] == "fake-gpt-fallback"


@pytest.mark.resilience
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "FINDING-001: LiteLLM router dispatches retry to other deployment in 0.02s, "
        "bypassing Retry-After wait"
    ),
)
def test_retry_429_honors_retry_after(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    # 1. Script 429 with retry-after 2, then 200
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {"status": 429, "retry_after": 2, "error_message": "Rate limited by upstream"},
                {"status": 200, "response_text": "ok after retry"},
            ]
        },
        timeout=5.0,
    )

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"{litellm_base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": "fake-primary",
                "messages": [{"role": "user", "content": "test 429 backoff"}],
            },
        )
        assert resp.status_code == 200

    attempts_resp = httpx.get(f"{fake_upstream_server.base_url}/control/attempts", timeout=5.0)
    attempts = attempts_resp.json()
    assert len(attempts) >= 2, f"Expected at least 2 attempts, got {len(attempts)}"
    wait_time = attempts[1]["timestamp"] - attempts[0]["timestamp"]
    assert (
        wait_time >= 2.0
    ), (
        f"Expected retry wait >= 2.0s per Retry-After header, "
        f"but retry occurred after {wait_time:.2f}s"
    )


@pytest.mark.resilience
def test_no_retry_on_400(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    # 1. Script 400
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {"status": 400, "error_message": "Bad request invalid argument"},
                {"status": 200, "response_text": "should not be called"},
            ]
        },
        timeout=5.0,
    )

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            f"{litellm_base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": "fake-fallback",
                "messages": [{"role": "user", "content": "test 400 no retry"}],
            },
        )
        assert resp.status_code == 400

    # Assert exactly 1 attempt with NO retry
    attempts_resp = httpx.get(f"{fake_upstream_server.base_url}/control/attempts", timeout=5.0)
    attempts = attempts_resp.json()
    assert len(attempts) == 1, f"Expected exactly 1 attempt on HTTP 400, got {len(attempts)}"
    assert attempts[0]["response_status"] == 400
