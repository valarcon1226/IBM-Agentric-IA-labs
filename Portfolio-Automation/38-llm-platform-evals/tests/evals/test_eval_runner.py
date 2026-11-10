"""Unit tests for evals.run with a fake client (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from evals import run as runner

REFUSAL = "I don't know based on the provided documentation."
PATHS = {"a.md", "b.md"}

ITEMS = [
    {
        "id": "Q1",
        "answerable": True,
        "question": "boom",
        "gold_doc_paths": ["a.md"],
        "key_fact_regexes": ["alpha"],
    },
    {
        "id": "Q2",
        "answerable": True,
        "question": "ok",
        "gold_doc_paths": ["a.md"],
        "key_fact_regexes": ["alpha"],
    },
    {
        "id": "Q3",
        "answerable": False,
        "question": "off topic",
        "gold_doc_paths": [],
        "key_fact_regexes": [],
    },
]


class FakeClient:
    def top_sources(self, question: str, n: int = 5) -> list[str]:
        return ["a.md", "b.md"]

    def ask(self, question: str) -> tuple[str, list[str]]:
        if question == "boom":
            raise TimeoutError("model too slow")
        if question == "off topic":
            return REFUSAL, []
        return "Alpha is the answer [1].", ["a.md", "b.md"]


def test_extract_citations() -> None:
    sources = ["a.md", "b.md"]
    assert runner.extract_citations("x [1] y [2] [9] [a__b.md] [ ] z", sources) == [
        "a.md",
        "b.md",
        "9",
        "a/b.md",
    ]
    assert runner.extract_citations("no cites", sources) == []


def test_failed_call_does_not_stop_run_and_outputs_are_written(tmp_path: Path) -> None:
    answers = tmp_path / "answers.jsonl"
    per_pass = runner.run(FakeClient(), ITEMS, 2, answers, PATHS)

    rows = [json.loads(line) for line in answers.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 6  # 3 questions x 2 passes, none lost
    failed = [r for r in rows if r["id"] == "Q1"]
    assert all(r["answer"] == "" and "TimeoutError" in r["error"] for r in failed)
    assert all("error" not in r for r in rows if r["id"] != "Q1")

    assert len(per_pass) == 2
    for metrics_ in per_pass:
        assert metrics_["hit_at_5"] == 1.0
        assert metrics_["key_fact_correctness"] == 0.5  # Q1 failed, Q2 correct
        assert metrics_["refusal_rate"] == 1.0
        assert metrics_["false_refusal_rate"] == 0.0
        assert metrics_["citation_validity"] == 1.0
        assert metrics_["errors"] == 1.0

    report = runner.build_report(per_pass, {"model": "fake"}, None)
    assert report["summary"]["key_fact_correctness"] == {"mean": 0.5, "min": 0.5, "max": 0.5}
    assert report["threshold_pass"]["key_fact_correctness"] is False
    assert "regression_pass" not in report

    baseline = {"summary": {"key_fact_correctness": {"mean": 0.9}}}
    with_base = runner.build_report(per_pass, {"model": "fake"}, baseline)
    assert with_base["regression_pass"] == {"key_fact_correctness": False}
