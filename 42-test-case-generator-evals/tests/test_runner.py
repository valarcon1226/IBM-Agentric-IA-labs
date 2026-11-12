"""Tests for evals.runner execution, threshold evaluations, and resilience."""

from __future__ import annotations

from pathlib import Path

from app.llm import StubLLM
from evals.runner import run_evaluation


def test_runner_runs_stub_dev_split(tmp_path: Path) -> None:
    # Standard run using StubLLM on dev split
    base_dir = Path(__file__).resolve().parent.parent
    golden_dir = base_dir / "evals" / "golden"
    config_file = base_dir / "evals" / "config.toml"

    payload, json_path, md_path = run_evaluation(
        model_name="stub",
        split="dev",
        golden_dir_path=golden_dir,
        config_path=config_file,
        output_dir_path=tmp_path / "stub",
    )

    assert payload["model"] == "stub"
    assert payload["split"] == "dev"
    assert payload["total_requirements"] == 8
    assert payload["total_test_cases"] > 0

    metrics = payload["metrics"]
    assert metrics["schema_valid_rate"]["passed"] is True
    assert metrics["verified_coverage"]["passed"] is True
    assert metrics["hallucinated_refs"]["passed"] is True
    assert metrics["duplicate_rate"]["passed"] is True
    assert metrics["negative_presence"]["passed"] is True

    assert json_path.is_file()
    assert md_path.is_file()

    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()
    assert "# Test Case Generator Evaluation Report — `stub`" in md_text
    assert "✅ PASS" in md_text


def test_runner_terminates_when_model_always_fails(tmp_path: Path) -> None:
    # Critical requirement: runner must terminate cleanly even if LLM always fails
    base_dir = Path(__file__).resolve().parent.parent
    golden_dir = base_dir / "evals" / "golden"
    config_file = base_dir / "evals" / "config.toml"

    failing_llm = StubLLM(always_fail=True)

    payload, json_path, md_path = run_evaluation(
        model_name="failing-model",
        split="dev",
        golden_dir_path=golden_dir,
        config_path=config_file,
        output_dir_path=tmp_path / "failing",
        custom_llm=failing_llm,
    )

    # Runner finished cleanly
    assert payload["total_requirements"] == 8
    assert payload["total_test_cases"] == 0

    metrics = payload["metrics"]
    assert metrics["schema_valid_rate"]["score"] == 0.0
    assert metrics["schema_valid_rate"]["passed"] is False

    assert json_path.is_file()
    assert md_path.is_file()

    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()
    assert "❌ FAIL" in md_text
