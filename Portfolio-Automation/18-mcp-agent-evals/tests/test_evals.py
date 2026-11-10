"""Tests executing the 30-case evaluation suite."""

from __future__ import annotations

import httpx
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


@pytest.mark.asyncio
async def test_suite_survives_llm_errors(monkeypatch, tmp_path):
    """A model that times out fails every case; the suite still finishes and reports."""

    class BrokenLLM:
        def __init__(self, model=None):
            self.model = model

        async def decide_action(self, **kwargs):
            raise httpx.ReadTimeout("slow model")

    monkeypatch.setattr("evals.runner.OpenAILLM", BrokenLLM)
    res = await run_eval_suite(model_name="broken", reports_dir=tmp_path)

    assert res["total_cases"] == 30
    assert res["passed_cases"] == 0
    assert (tmp_path / "eval.json").exists()


@pytest.mark.asyncio
async def test_runs_do_not_share_reservations(tmp_path):
    """Each run starts from an empty database.

    Reservations kept from earlier runs would fill the 40-seat slots and make a valid booking
    fail on the fourth run.
    """
    for _ in range(4):
        res = await run_eval_suite(model_name="fake", reports_dir=tmp_path)
        assert res["passed_cases"] == 30
