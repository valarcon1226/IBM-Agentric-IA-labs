"""Backpressure and overload test for Keycloak token endpoint under concurrent request bursts.

Validates:
- Quarkus/Keycloak HTTP max queued requests load shedding (`--http-max-queued-requests`).
- OWASP ASVS v4.0.3 Chapter V13 (API and Web Service Verification) / REQ-IAM-005.
- Target: 0 unhandled 5xx (500) internal errors during 300-request burst (503 allowed).
- Immediate recovery: single request 2 seconds after the burst succeeds with 200 OK.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from collections import Counter
from typing import Generator

import httpx
import pytest
from qa_common.targets import assert_target


def _wait_for_keycloak_ready(base_url: str, timeout_s: float = 40.0) -> None:
    start = time.monotonic()
    mgmt_url = "http://127.0.0.1:9000/health/ready"
    while time.monotonic() - start < timeout_s:
        try:
            resp = httpx.get(mgmt_url, timeout=2.0)
            if resp.status_code == 200 and resp.json().get("status") == "UP":
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise TimeoutError(f"Keycloak did not report ready within {timeout_s}s")


def _restart_keycloak_with_max_queued(queued_requests: int) -> None:
    env = os.environ.copy()
    env["KC_HTTP_MAX_QUEUED_REQUESTS"] = str(queued_requests)
    cmd = ["docker", "compose", "up", "-d", "keycloak"]
    subprocess.run(cmd, env=env, check=True, capture_output=True)
    _wait_for_keycloak_ready("http://127.0.0.1:8081")


@pytest.fixture(scope="module")
def keycloak_low_queue() -> Generator[None, None, None]:
    """Restart Keycloak with http-max-queued-requests set low (20), then restore to 1000."""
    _restart_keycloak_with_max_queued(20)
    try:
        yield
    finally:
        _restart_keycloak_with_max_queued(1000)


@pytest.mark.resilience
@pytest.mark.req("REQ-IAM-005")
def test_backpressure_sheds_load_with_503_and_recovers(
    keycloak_low_queue: None,
    base_url: str,
) -> None:
    """Fire 300 concurrent token requests: assert 0 500s, rejections are 503, recovery in 2s."""
    token_url = f"{base_url}/realms/identity-realm/protocol/openid-connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": "service-account-client",
        "client_secret": "service-account-secret-1234",
    }

    async def _execute_burst() -> tuple[Counter[int], int]:
        limits = httpx.Limits(max_connections=350, max_keepalive_connections=350)
        async with httpx.AsyncClient(limits=limits, timeout=20.0) as client:
            async def _send() -> int:
                try:
                    r = await client.post(token_url, data=payload)
                    return r.status_code
                except Exception:
                    return 500

            tasks = [_send() for _ in range(300)]
            statuses = await asyncio.gather(*tasks)
            counts = Counter(statuses)

            # Wait 2 seconds and verify immediate recovery
            await asyncio.sleep(2.0)
            recovery_resp = await client.post(token_url, data=payload)
            return counts, recovery_resp.status_code

    counts, recovery_status = asyncio.run(_execute_burst())

    # 1. Assert no 500 Internal Server Errors occurred
    unhandled_500_errors = counts.get(500, 0)
    assert unhandled_500_errors == 0, f"Expected 0 500 errors, got: {unhandled_500_errors}"
    assert_target("burst_5xx_errors", float(unhandled_500_errors))

    # 2. Assert every rejection is 503 (Server not Available / Service Unavailable)
    for code in counts:
        if code != 200:
            assert code == 503, f"Unexpected non-503 rejection status: {code}"

    # 3. Assert backpressure actually triggered load shedding
    assert counts.get(503, 0) > 0, (
        f"Expected 503 rejections under 300 concurrent requests with queue=20, got: {counts}"
    )

    # 4. Assert single request 2s after burst succeeds
    assert recovery_status == 200, (
        f"Server failed to recover 2s after burst; status={recovery_status}"
    )
