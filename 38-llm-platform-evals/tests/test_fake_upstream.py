"""Unit tests for Fake Upstream (Test Double).

Validates each scripted behavior:
- ok (non-streaming and streaming)
- 429 with retry-after
- 500 internal server error
- delay of N ms
- cut stream after K chunks
- 400 bad request
- attempt log logging and retrieval
"""

from __future__ import annotations

import json
import time
from typing import Generator

import httpx
import pytest

from tests.fake_upstream import FakeUpstreamServer


@pytest.fixture(scope="module")
def upstream_server() -> Generator[FakeUpstreamServer, None, None]:
    server = FakeUpstreamServer(host="127.0.0.1", port=8099)
    server.start()
    time.sleep(0.1)
    yield server
    server.stop()


@pytest.fixture(autouse=True)
def reset_server(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(f"{upstream_server.base_url}/control/reset", timeout=5.0)


def test_fake_upstream_health(upstream_server: FakeUpstreamServer) -> None:
    resp = httpx.get(f"{upstream_server.base_url}/health", timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["double"] == "fake_upstream"


def test_behavior_ok_non_streaming(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 200, "response_text": "Custom OK response"}]},
        timeout=5.0,
    )
    resp = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={
            "model": "fake-primary",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
        timeout=5.0,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "Custom OK response"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert "usage" in body


def test_behavior_ok_streaming(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 200, "response_text": "One two three"}]},
        timeout=5.0,
    )
    with httpx.stream(
        "POST",
        f"{upstream_server.base_url}/v1/chat/completions",
        json={
            "model": "fake-primary",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
        timeout=5.0,
    ) as stream_resp:
        assert stream_resp.status_code == 200
        lines = [line.strip() for line in stream_resp.iter_lines() if line.strip()]
        assert any("data: [DONE]" in line_item for line_item in lines)
        data_chunks = [
            json.loads(line_item.replace("data: ", ""))
            for line_item in lines
            if line_item.startswith("data: {")
        ]
        assert len(data_chunks) >= 3
        assert data_chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_behavior_429_with_retry_after(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {"status": 429, "retry_after": 3, "error_message": "Rate limit exceeded"}
            ]
        },
        timeout=5.0,
    )
    resp = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
        timeout=5.0,
    )
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "3"
    err = resp.json()["error"]
    assert err["code"] == 429
    assert "Rate limit exceeded" in err["message"]


def test_behavior_500_server_error(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 500, "error_message": "Upstream internal failure"}]},
        timeout=5.0,
    )
    resp = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
        timeout=5.0,
    )
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == 500


def test_behavior_delay(upstream_server: FakeUpstreamServer) -> None:
    delay_ms = 250
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {"status": 200, "delay_ms": delay_ms, "response_text": "Delayed response"}
            ]
        },
        timeout=5.0,
    )
    start = time.perf_counter()
    resp = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
        timeout=5.0,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms >= 240  # Allow slight timing tolerance


def test_behavior_cut_stream(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 200, "cut_after_chunks": 2, "response_text": "A B C D"}]},
        timeout=5.0,
    )
    chunks_received = []
    has_stop = False
    has_done = False
    try:
        with httpx.stream(
            "POST",
            f"{upstream_server.base_url}/v1/chat/completions",
            json={
                "model": "fake-primary",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            timeout=5.0,
        ) as stream_resp:
            for line in stream_resp.iter_lines():
                if not line.strip():
                    continue
                if "data: [DONE]" in line:
                    has_done = True
                if line.startswith("data: {"):
                    parsed = json.loads(line.replace("data: ", ""))
                    chunks_received.append(parsed)
                    if parsed["choices"][0]["finish_reason"] == "stop":
                        has_stop = True
    except (httpx.RemoteProtocolError, httpx.ReadError):
        pass

    assert not has_done
    assert not has_stop
    assert len(chunks_received) == 2


def test_behavior_400_bad_request(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 400, "error_message": "Invalid temperature parameter"}]},
        timeout=5.0,
    )
    resp = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={"model": "fake-primary", "messages": [{"role": "user", "content": "hi"}]},
        timeout=5.0,
    )
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["type"] == "invalid_request_error"
    assert "Invalid temperature parameter" in err["message"]


def test_attempt_log_recording(upstream_server: FakeUpstreamServer) -> None:
    httpx.post(
        f"{upstream_server.base_url}/control/script",
        json={"behaviors": [{"status": 500}, {"status": 200, "response_text": "Success"}]},
        timeout=5.0,
    )

    resp1 = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={"model": "fake-primary", "messages": [{"role": "user", "content": "attempt 1"}]},
        headers={"X-Test-Id": "run-001"},
        timeout=5.0,
    )
    assert resp1.status_code == 500

    resp2 = httpx.post(
        f"{upstream_server.base_url}/v1/chat/completions",
        json={"model": "fake-primary", "messages": [{"role": "user", "content": "attempt 2"}]},
        headers={"X-Test-Id": "run-002"},
        timeout=5.0,
    )
    assert resp2.status_code == 200

    attempts_resp = httpx.get(f"{upstream_server.base_url}/control/attempts", timeout=5.0)
    attempts = attempts_resp.json()
    assert len(attempts) == 2
    assert attempts[0]["response_status"] == 500
    assert attempts[0]["headers"]["x-test-id"] == "run-001"
    assert attempts[0]["body"]["messages"][0]["content"] == "attempt 1"
    assert attempts[1]["response_status"] == 200
    assert attempts[1]["headers"]["x-test-id"] == "run-002"
