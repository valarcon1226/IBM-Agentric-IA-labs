"""Pure metric functions for the pre-registered protocol in docs/EVALS.md (sections 3 and 4)."""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence

REFUSAL_SENTENCE = "I don't know based on the provided documentation."
THRESHOLDS = {
    "hit_at_5": 0.85,
    "key_fact_correctness": 0.75,
    "refusal_rate": 0.90,
    "false_refusal_rate": 0.10,
    "citation_validity": 1.00,
}
LOWER_IS_BETTER = {"false_refusal_rate"}
REGRESSION_TOLERANCE = 0.03


def _norm(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'").replace("`", "'").lower()


def is_refusal(answer: str) -> bool:
    return _norm(REFUSAL_SENTENCE) in _norm(answer)


def _rate(flags: Sequence[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def hit_at_5(gold_paths: Sequence[Collection[str]], top_sources: Sequence[Sequence[str]]) -> float:
    """Per answerable question: any gold path among the top 5 sources."""
    return _rate([bool(set(g) & set(t[:5])) for g, t in zip(gold_paths, top_sources, strict=True)])


def key_fact_correctness(answers: Sequence[str], regexes: Sequence[Sequence[str]]) -> float:
    """Per answerable question: every regex matches the answer (case-insensitive)."""
    return _rate(
        [
            all(re.search(r, a, re.IGNORECASE) for r in rs)
            for a, rs in zip(answers, regexes, strict=True)
        ]
    )


def refusal_rate(answers: Sequence[str]) -> float:
    """Rate over answers; use on unanswerable questions (RR) or answerable ones (FRR)."""
    return _rate([is_refusal(a) for a in answers])


def citation_validity(
    citations: Sequence[Sequence[str]],
    top_sources: Sequence[Sequence[str]],
    corpus_paths: Collection[str],
) -> float:
    """A question is valid when every citation is a top source and a corpus file.

    No citations counts as valid.
    """
    return _rate(
        [
            all(c in t and c in corpus_paths for c in cs)
            for cs, t in zip(citations, top_sources, strict=True)
        ]
    )


def summarize(values: Sequence[float]) -> dict[str, float]:
    return {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}


def regression_check(
    current_means: dict[str, float], baseline_means: dict[str, float]
) -> dict[str, bool]:
    """True per metric when it passes: not more than 0.03 worse than baseline."""
    result = {}
    for name, base in baseline_means.items():
        if name not in current_means:
            continue
        cur = current_means[name]
        worse = cur - base if name in LOWER_IS_BETTER else base - cur
        result[name] = worse <= REGRESSION_TOLERANCE + 1e-9
    return result


def threshold_check(means: dict[str, float]) -> dict[str, bool]:
    return {
        name: (means[name] <= t if name in LOWER_IS_BETTER else means[name] >= t)
        for name, t in THRESHOLDS.items()
        if name in means
    }
