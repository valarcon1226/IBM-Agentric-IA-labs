"""Unit tests for scripts.retrieval_check (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import retrieval_check as rc

EVALS = Path(__file__).resolve().parents[2] / "evals"
REC = {"gold_doc_paths": ["g.md"], "key_fact_regexes": ["alpha", "beta"]}


def check(run: list[str], wide5: list[str], facts: int = 2) -> dict:
    return {"run": run, "wide5": wide5, "gold_in_wide5": "g.md" in wide5, "facts_in_wide5": facts}


def test_category_by_what_reached_the_model() -> None:
    assert rc.category(check(["x.md"], ["g.md"]), REC) == "search_dropped_gold_chunk"
    assert rc.category(check(["x.md"], ["y.md"]), REC) == "gold_not_retrieved"
    assert rc.category(check(["g.md", "x.md"], ["g.md", "y.md"]), REC) == "other_chunks_differ"
    one_fact = check(["g.md", "x.md"], ["x.md", "g.md"], facts=1)
    assert rc.category(one_fact, REC) == "fact_not_in_chunks"
    assert rc.category(check(["g.md", "x.md"], ["x.md", "g.md"]), REC) == "facts_in_chunks"


def test_outcome() -> None:
    assert rc.outcome({**REC, "answer": "Alpha and beta."}) == "correct"
    assert rc.outcome({**REC, "answer": "Only alpha."}) == "incomplete"
    refusal = "I don't know based on the provided documentation."
    assert rc.outcome({**REC, "answer": refusal}) == "refused"


def test_committed_check_matches_the_baseline_run() -> None:
    """The numbers quoted in docs/EVAL-RESULTS.md come from these two committed files."""
    checks = json.loads((EVALS / "retrieval_check.json").read_text("utf-8"))
    summary = rc.summarize(checks, EVALS / "baseline_answers.jsonl")
    table = summary["table"]
    assert summary["questions"] == 96
    assert sum(row["correct"] for row in table.values()) == 68  # key-fact correctness 68/96
    assert sum(row["refused"] for row in table.values()) == 12  # false refusal rate 12/96
    assert table["search_dropped_gold_chunk"] == {"correct": 0, "incomplete": 0, "refused": 5}
    assert table["facts_in_chunks"] == {"correct": 60, "incomplete": 4, "refused": 2}
    assert (summary["run_equals_wide5"], summary["k5_equals_wide5"]) == (79, 79)
