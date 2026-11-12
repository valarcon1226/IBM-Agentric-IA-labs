"""Unit tests for evals.metrics (no network)."""

from __future__ import annotations

import pytest

from evals import metrics as m


def test_hit_at_5_uses_only_top_five() -> None:
    gold = [["a.md"], ["b.md"], ["c.md"]]
    top = [["x.md", "a.md"], ["1", "2", "3", "4", "5", "b.md"], ["z.md"]]
    assert m.hit_at_5(gold, top) == pytest.approx(1 / 3)


def test_key_fact_requires_all_regexes_case_insensitive() -> None:
    answers = ["The Kubelet and the container runtime", "only kubelet"]
    regexes = [["kubelet", "container runtime"]] * 2
    assert m.key_fact_correctness(answers, regexes) == 0.5


@pytest.mark.parametrize(
    "answer",
    [
        "I don't know based on the provided documentation.",
        "i DON'T know based on the provided documentation.",
        "I don’t know based on the provided documentation.",
        "Sorry. I don't know based on the provided documentation. Try elsewhere.",
    ],
)
def test_refusal_detected(answer: str) -> None:
    assert m.is_refusal(answer)


def test_refusal_not_detected_and_rates() -> None:
    assert not m.is_refusal("The kubelet runs pods.")
    assert not m.is_refusal("")
    answers = ["I don't know based on the provided documentation.", "An answer"]
    assert m.refusal_rate(answers) == 0.5
    assert m.refusal_rate([]) == 0.0


def test_citation_validity_cases() -> None:
    corpus = {"a.md", "b.md", "c.md"}
    top = [["a.md", "b.md"]] * 4
    cites = [
        [],  # no citations is valid
        ["a.md"],  # valid
        ["c.md"],  # in corpus but not a top source
        ["a.md", "ghost.md"],  # hallucinated file
    ]
    assert m.citation_validity(cites, top, corpus) == 0.5


def test_summarize() -> None:
    assert m.summarize([0.5, 0.7, 0.9]) == {"mean": pytest.approx(0.7), "min": 0.5, "max": 0.9}


def test_regression_check_directions() -> None:
    base = {"hit_at_5": 0.90, "false_refusal_rate": 0.05, "refusal_rate": 0.95}
    ok = {"hit_at_5": 0.87, "false_refusal_rate": 0.08, "refusal_rate": 0.99}
    assert all(m.regression_check(ok, base).values())  # exactly 0.03 worse still passes
    bad = {"hit_at_5": 0.86, "false_refusal_rate": 0.09, "refusal_rate": 0.90}
    assert m.regression_check(bad, base) == {
        "hit_at_5": False,
        "false_refusal_rate": False,
        "refusal_rate": False,
    }
    better_frr = {"hit_at_5": 0.9, "false_refusal_rate": 0.0, "refusal_rate": 0.95}
    assert all(m.regression_check(better_frr, base).values())


def test_threshold_check() -> None:
    means = {
        "hit_at_5": 0.85,
        "key_fact_correctness": 0.74,
        "refusal_rate": 0.9,
        "false_refusal_rate": 0.11,
        "citation_validity": 1.0,
    }
    assert m.threshold_check(means) == {
        "hit_at_5": True,
        "key_fact_correctness": False,
        "refusal_rate": True,
        "false_refusal_rate": False,
        "citation_validity": True,
    }
