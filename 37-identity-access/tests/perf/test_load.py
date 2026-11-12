"""Load performance test suite for OAuth 2.0 token issuance and password authentication.

Measures:
1. Token endpoint (client_credentials) at 10, 50, and 100 rps.
2. Direct Access Grants (password login) at 10, 50, and 100 rps.
Records p50, p95, p99 in results/metrics.json and asserts SLAs from targets.toml:
- token_p95_at_50rps_ms <= 300.0 ms
- login_p95_at_10rps_ms <= 800.0 ms
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from qa_common.targets import assert_target


async def _measure_endpoint_rate(
    url: str,
    payload: dict[str, str],
    target_rps: int,
    duration_s: float = 4.0,
) -> list[float]:
    """Send requests at approximately target_rps and return latencies in milliseconds."""
    interval = 1.0 / target_rps
    latencies_ms: list[float] = []
    limits = httpx.Limits(max_connections=150, max_keepalive_connections=150)

    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        end_time = time.monotonic() + duration_s
        while time.monotonic() < end_time:
            t0 = time.monotonic()

            # Dynamic username rotation for password login
            body = dict(payload)
            if "username" in body and body["username"] == "ROTATE_BENCH_USER":
                idx = random.randint(100, 1100)
                body["username"] = f"bench_user_{idx:05d}"

            try:
                resp = await client.post(url, data=body)
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                if resp.status_code == 200:
                    latencies_ms.append(elapsed_ms)
            except Exception:
                pass

            sleep_time = interval - (time.monotonic() - t0)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    return latencies_ms


def _compute_percentiles(samples: list[float]) -> dict[str, float]:
    assert samples, "No latency samples collected"
    count = len(samples)
    if count < 100:
        samples_sorted = sorted(samples)
        p50 = statistics.median(samples_sorted)
        p95 = samples_sorted[int(count * 0.95)]
        p99 = samples_sorted[min(int(count * 0.99), count - 1)]
    else:
        q = statistics.quantiles(samples, n=100, method="inclusive")
        p50 = q[49]
        p95 = q[94]
        p99 = q[98]
    return {
        "count": float(count),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
    }


def _update_metrics_json(key: str, data: dict[str, Any]) -> None:
    os.makedirs("results", exist_ok=True)
    metrics_path = Path("results/metrics.json")
    existing: dict[str, Any] = {}
    if metrics_path.exists():
        try:
            with metrics_path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing[key] = data
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


@pytest.mark.perf
@pytest.mark.req("REQ-IAM-005")
def test_client_credentials_token_latency(base_url: str) -> None:
    """Measure client_credentials at 10, 50, and 100 rps and assert p95 target at 50 rps."""
    token_url = f"{base_url}/realms/identity-realm/protocol/openid-connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": "service-account-client",
        "client_secret": "service-account-secret-1234",
    }

    rates = [10, 50, 100]
    rate_results: dict[int, dict[str, float]] = {}

    for rps in rates:
        # At least 3 repeat measurement bursts
        all_samples: list[float] = []
        for _ in range(3):
            samples = asyncio.run(_measure_endpoint_rate(token_url, payload, target_rps=rps))
            all_samples.extend(samples)

        stats = _compute_percentiles(all_samples)
        rate_results[rps] = stats
        _update_metrics_json(f"client_credentials_{rps}rps", stats)

    # Validate target SLA at 50 rps
    p95_50 = rate_results[50]["p95_ms"]
    assert_target("token_p95_at_50rps_ms", p95_50)


@pytest.mark.perf
@pytest.mark.req("REQ-IAM-005")
def test_password_login_latency(base_url: str) -> None:
    """Measure password login at 10, 50, and 100 rps and assert p95 target at 10 rps."""
    token_url = f"{base_url}/realms/identity-realm/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": "confidential-web-app",
        "client_secret": "confidential-secret-1234",
        "username": "ROTATE_BENCH_USER",
        "password": "Password123!",
    }

    rates = [10, 50, 100]
    rate_results: dict[int, dict[str, float]] = {}

    for rps in rates:
        all_samples: list[float] = []
        for _ in range(3):
            samples = asyncio.run(_measure_endpoint_rate(token_url, payload, target_rps=rps))
            all_samples.extend(samples)

        stats = _compute_percentiles(all_samples)
        rate_results[rps] = stats
        _update_metrics_json(f"password_login_{rps}rps", stats)

    # Validate target SLA at 10 rps
    p95_10 = rate_results[10]["p95_ms"]
    assert_target("login_p95_at_10rps_ms", p95_10)
