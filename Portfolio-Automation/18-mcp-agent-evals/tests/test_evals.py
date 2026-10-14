"""Tests executing the 30-case evaluation suite."""

from __future__ import annotations

import pytest

from evals.runner import run_eval_suite


@pytest.mark.asyncio
async def test_evaluation_suite(model_name: str):
    """Execute the full 30-case evaluation suite.

    With the deterministic fake model, this must achieve exactly 100% across all 5 metrics.
    With an external model passed via --model, executes and records accuracy.
    """
    res = await run_eval_suite(model_name=model_name)

    assert res["total_cases"] == 30, f"Expected 30 evaluation cases, got {res['total_cases']}"

    if model_name.lower() in ("fake", "deterministic"):
        # Deterministic suite must achieve 100%
        assert res["passed_cases"] == 30, (
            f"Expected 30 passed cases with fake model, got {res['passed_cases']}"
        )
        assert res["overall_accuracy"] == 1.0, (
            f"Expected 1.0 accuracy with fake model, got {res['overall_accuracy']}"
        )

        for m_name, m_data in res["metrics"].items():
            assert m_data["rate"] == 1.0, (
                f"Metric '{m_name}' did not achieve 100%: rate={m_data['rate']}"
            )
    else:
        # Real model run: verify results were recorded and report exists
        assert res["total_cases"] > 0
        assert 0.0 <= res["overall_accuracy"] <= 1.0
