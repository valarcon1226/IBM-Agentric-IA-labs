"""Shared pytest fixtures and configuration for 38-llm-platform-evals."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Generator

import httpx
import pytest

from tests.fake_upstream import FakeUpstreamServer


@pytest.fixture(scope="session")
def litellm_base_url() -> str:
    return os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")


@pytest.fixture(scope="session")
def litellm_master_key() -> str:
    key = os.getenv("LITELLM_MASTER_KEY")
    if not key:
        pytest.fail(
            "LITELLM_MASTER_KEY environment variable is not set. "
            "Please export LITELLM_MASTER_KEY before running tests."
        )
    return key


@pytest.fixture(scope="session")
def fake_upstream_server() -> Generator[FakeUpstreamServer, None, None]:
    """Runs the fake upstream test double on port 8001 for the entire test session."""
    server = FakeUpstreamServer(host="127.0.0.1", port=8001)
    server.start()
    time.sleep(0.2)
    yield server
    server.stop()


@pytest.fixture
def create_test_key(
    litellm_base_url: str,
    litellm_master_key: str,
) -> Callable[..., Dict[str, Any]]:
    """Factory fixture to generate isolated LiteLLM virtual keys."""

    def _factory(**kwargs: Any) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {litellm_master_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "key_alias": kwargs.get("key_alias", f"key-{int(time.time()*1000)}"),
            "models": kwargs.get("models", ["fake-primary", "fake-fallback", "primary-model"]),
            **kwargs,
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{litellm_base_url}/key/generate", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    return _factory


def wait_until(
    condition: Callable[[], bool],
    description: str,
    timeout: float = 60.0,
    interval: float = 0.5,
) -> None:
    """Wait on condition with explicit timeout and descriptive failure message.

    Adheres strictly to the rule prohibiting arbitrary time.sleep in test assertions.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise TimeoutError(f"Condition not met after {timeout}s: {description}")
