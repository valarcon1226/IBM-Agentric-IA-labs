"""API tests for cost accounting accuracy and budget cap enforcement.

Verifies:
1. REQ-LLM-007: Gateway tracks exact spend per virtual key based on token usage and model pricing.
   - 50 requests through LiteLLM with model 'fake-cost'.
   - Expected cost computed from prompt/completion tokens and litellm/config.yaml prices.
   - Compare with spend recorded by LiteLLM: tolerance within <= +-1.0%.
2. REQ-LLM-008: Virtual key max_budget enforcement.
   - Virtual key with max_budget = 0.05 USD.
   - Requests sent until blocked.
   - Spend recorded at moment of blocking exceeds max_budget by at most 1 request's cost.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict

import httpx
import pytest
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target

from tests.conftest import wait_until
from tests.fake_upstream import FakeUpstreamServer


def load_model_pricing(config_path: Path, model_name: str) -> tuple[float, float]:
    """Extract (input_cost_per_token, output_cost_per_token) from litellm/config.yaml."""
    in_price = 0.0
    out_price = 0.0
    in_target_model = False
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("- model_name:"):
                current_model = stripped.split(":", 1)[1].strip().strip("\"'")
                in_target_model = (current_model == model_name)
            elif in_target_model:
                if stripped.startswith("input_cost_per_token:"):
                    in_price = float(stripped.split(":", 1)[1].strip())
                elif stripped.startswith("output_cost_per_token:"):
                    out_price = float(stripped.split(":", 1)[1].strip())
                elif stripped.startswith("router_settings:") or stripped.startswith(
                    "litellm_settings:"
                ):
                    break
    if in_price > 0.0 and out_price > 0.0:
        return in_price, out_price
    raise ValueError(f"Pricing for {model_name} not found in {config_path}")


@pytest.mark.api
def test_cost_accounting_50_requests(
    litellm_base_url: str,
    litellm_master_key: str,
    create_test_key: Callable[..., Dict[str, Any]],
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    """Send 50 requests through LiteLLM and verify spend matches token pricing within +-1%."""
    config_file = Path(__file__).resolve().parent.parent.parent / "litellm" / "config.yaml"
    input_price, output_price = load_model_pricing(config_file, "fake-cost")
    assert input_price > 0 and output_price > 0, "Pricing must be defined in litellm/config.yaml"

    # Reset upstream to clean state
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)

    # Create dedicated key for 50 requests test
    key_info = create_test_key(
        key_alias=f"test-cost-accounting-50-{uuid.uuid4().hex[:8]}",
        models=["fake-cost"],
    )
    test_key = key_info["key"]

    total_expected_cost = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    with httpx.Client(base_url=litellm_base_url, timeout=15.0) as client:
        # Send 50 requests rapidly before batch writing interval fires
        for i in range(50):
            res = client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {test_key}"},
                json={
                    "model": "fake-cost",
                    "messages": [{"role": "user", "content": f"Req {i}: order state"}],
                },
            )
            assert res.status_code == 200, f"Request {i} failed: {res.text}"
            data = res.json()
            usage = data.get("usage", {})
            p_tokens = usage.get("prompt_tokens", 0)
            c_tokens = usage.get("completion_tokens", 0)
            assert p_tokens > 0 and c_tokens > 0, f"Usage missing in response {i}: {data}"

            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            req_cost = (p_tokens * input_price) + (c_tokens * output_price)
            total_expected_cost += req_cost
            time.sleep(0.01)

        # Wait for LiteLLM spend batcher to flush spend to DB
        def _get_spend() -> float:
            resp = client.get(
                f"/key/info?key={test_key}",
                headers={"Authorization": f"Bearer {litellm_master_key}"},
            )
            assert resp.status_code == 200, f"Failed to get key info: {resp.text}"
            return float(resp.json()["info"].get("spend", 0.0))

        # Poll until spend reaches expected cost (within tolerance)
        wait_until(
            lambda: _get_spend() >= total_expected_cost * 0.99,
            description=f"LiteLLM proxy spend flush to DB (target: {total_expected_cost})",
            timeout=60.0,
            interval=0.5,
        )

        recorded_spend = _get_spend()

    diff_abs = abs(recorded_spend - total_expected_cost)
    diff_pct = (diff_abs / total_expected_cost) * 100.0

    # Save to metrics.json
    results_path = Path(__file__).resolve().parent.parent.parent / "results" / "metrics.json"
    recorder = MetricsRecorder()
    recorder.record("cost_50_req_expected_usd", total_expected_cost)
    recorder.record("cost_50_req_recorded_usd", recorded_spend)
    recorder.record("spend_accuracy_diff_pct", diff_pct)
    recorder.save(results_path)

    # Check against target (targets.toml: spend_accuracy_tolerance_pct <= 1.0%)
    assert_target("spend_accuracy_tolerance_pct", diff_pct)
    assert diff_pct <= 1.0, f"Spend difference {diff_pct:.4f}% exceeds +-1.0% tolerance"


@pytest.mark.api
def test_budget_cap_enforcement(
    litellm_base_url: str,
    litellm_master_key: str,
    create_test_key: Callable[..., Dict[str, Any]],
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    """Create key with max_budget 0.05, send until blocked, assert overspend <= 1 req cost."""
    config_file = Path(__file__).resolve().parent.parent.parent / "litellm" / "config.yaml"
    input_price, output_price = load_model_pricing(config_file, "fake-cost")

    max_budget = 0.05
    key_info = create_test_key(
        key_alias=f"test-budget-cap-key-{uuid.uuid4().hex[:8]}",
        max_budget=max_budget,
        models=["fake-cost"],
    )
    test_key = key_info["key"]

    # Single request cost with default response (15 prompt tokens, 2 completion tokens)
    cost_per_req = (15 * input_price) + (2 * output_price)

    blocked = False
    blocked_status_code = 0
    successful_requests = 0

    with httpx.Client(base_url=litellm_base_url, timeout=15.0) as client:
        def _get_spend() -> float:
            r = client.get(
                f"/key/info?key={test_key}",
                headers={"Authorization": f"Bearer {litellm_master_key}"},
            )
            assert r.status_code == 200
            return float(r.json()["info"].get("spend", 0.0))

        # Initial spend must be 0.0
        assert _get_spend() == 0.0

        for seq in range(1, 15):
            res = client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {test_key}"},
                json={
                    "model": "fake-cost",
                    "messages": [{"role": "user", "content": f"Seq {seq}: budget probe"}],
                },
            )

            if res.status_code in (400, 429):
                body = res.text.lower()
                if "budget" in body or "exceeded" in body or "limit" in body:
                    blocked = True
                    blocked_status_code = res.status_code
                    break

            assert res.status_code == 200, f"Unexpected error status {res.status_code}: {res.text}"
            successful_requests += 1

            # Wait until spend flush updates the key's spend before next request
            target_spend = successful_requests * cost_per_req
            wait_until(
                lambda: _get_spend() >= target_spend * 0.99,
                description=f"Spend reflects req {successful_requests} ({target_spend})",
                timeout=15.0,
                interval=0.5,
            )

        assert blocked, (
            f"Request not blocked after {successful_requests} reqs (budget: {max_budget})"
        )
        assert blocked_status_code in (400, 429)

        # Retrieve final recorded spend for the key
        wait_until(
            lambda: _get_spend() >= max_budget,
            description="Recorded spend reaches max_budget after blocking",
            timeout=15.0,
            interval=0.5,
        )

        spend_at_blocking = _get_spend()

    overspend = spend_at_blocking - max_budget
    assert overspend >= 0.0, f"Spend ({spend_at_blocking}) was less than budget ({max_budget})"
    # Target: spend recorded at blocking exceeds budget by at most 1 request's cost
    assert overspend <= cost_per_req + 1e-9, (
        f"Overspend {overspend:.6f} exceeds single request cost {cost_per_req:.6f} "
        f"(max allowed: {cost_per_req:.6f})"
    )

    # Save to metrics.json
    results_path = Path(__file__).resolve().parent.parent.parent / "results" / "metrics.json"
    recorder = MetricsRecorder()
    recorder.record("budget_max_usd", max_budget)
    recorder.record("budget_spend_at_blocking_usd", spend_at_blocking)
    recorder.record("budget_overspend_usd", overspend)
    recorder.record("budget_single_req_cost_usd", cost_per_req)
    recorder.record("budget_successful_requests_before_block", float(successful_requests))
    recorder.save(results_path)

    # Verify target: budget_overspend_max_requests <= 1
    overspend_requests = overspend / cost_per_req
    assert_target("budget_overspend_max_requests", 1)
    assert overspend_requests <= 1.0 + 1e-5
