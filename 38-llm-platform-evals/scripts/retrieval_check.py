"""Post-hoc retrieval check for an eval run. Retrieval only: no model call.

For every answerable question in the answers log it repeats the retrieval query twice: with k=5,
which is what the chat pipeline uses, and with k=200, a much wider search of the same approximate
index. It records the chunk files of both next to the ones logged during the run, and whether
the gold document and the key facts are in the first five chunks of the wide query.

    python -m scripts.retrieval_check --answers evals/baseline_answers.jsonl \
        --out evals/retrieval_check.json

When the output file already exists it is only summarised, so the committed file can be read
without the stack.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from evals import metrics
from evals import run as runner

PROJECT_DIR = Path(__file__).resolve().parent.parent
WIDE_K = 200
CATEGORIES = [
    "search_dropped_gold_chunk",  # a wider search ranks a gold chunk in the top five
    "gold_not_retrieved",  # no gold chunk in the run's five nor in the wide top five
    "fact_not_in_chunks",  # right document, a key fact is not in the five chunks
    "facts_in_chunks",  # every key fact is in the five chunks
    "other_chunks_differ",  # gold chunk present, the rest differs from the wide top five
]


def first_pass(answers: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in answers.read_text(encoding="utf-8").splitlines() if line]
    return {r["id"]: r for r in rows if r["pass"] == 1 and r["answerable"]}


def collect(answers: Path, golden: Path) -> dict[str, dict[str, Any]]:
    questions = {
        g["id"]: g["question"]
        for g in (json.loads(line) for line in golden.read_text(encoding="utf-8").splitlines())
    }
    client = runner.OpenWebUIClient(
        os.environ.get("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088"),
        "primary-model",
        "",
        300,
        0,
        0,
    )

    def query(text: str, k: int) -> tuple[list[str], list[float], list[str]]:
        resp = client.http.post(
            "/api/v1/retrieval/query/collection",
            json={"collection_names": [client.kid], "query": text, "k": k},
        )
        resp.raise_for_status()
        data = resp.json()
        names = [m["name"].replace(runner.SEP, "/") for m in data["metadatas"][0]]
        return names, [round(d, 4) for d in data["distances"][0]], data["documents"][0]

    out: dict[str, dict[str, Any]] = {}
    for qid, rec in first_pass(answers).items():
        k5, d5, _ = query(questions[qid], 5)
        wide, d_wide, texts = query(questions[qid], WIDE_K)
        context = "\n".join(texts[:5])
        gold = set(rec["gold_doc_paths"])
        out[qid] = {
            "run": [doc for group in rec.get("attached") or [] for doc in group],
            "k5": k5,
            "wide5": wide[:5],
            "k5_distances": d5,
            "wide5_distances": d_wide[:5],
            "gold_in_wide5": bool(gold & set(wide[:5])),
            "gold_in_wide_top5_documents": bool(gold & set(list(dict.fromkeys(wide))[:5])),
            "facts_in_wide5": sum(
                bool(re.search(x, context, re.IGNORECASE)) for x in rec["key_fact_regexes"]
            ),
        }
    return out


def outcome(rec: dict[str, Any]) -> str:
    if all(re.search(x, rec["answer"], re.IGNORECASE) for x in rec["key_fact_regexes"]):
        return "correct"
    return "refused" if metrics.is_refusal(rec["answer"]) else "incomplete"


def category(check: dict[str, Any], rec: dict[str, Any]) -> str:
    gold_in_run = bool(set(rec["gold_doc_paths"]) & set(check["run"]))
    if not gold_in_run:
        return "search_dropped_gold_chunk" if check["gold_in_wide5"] else "gold_not_retrieved"
    if sorted(check["run"]) != sorted(check["wide5"]):
        return "other_chunks_differ"
    all_facts = check["facts_in_wide5"] == len(rec["key_fact_regexes"])
    return "facts_in_chunks" if all_facts else "fact_not_in_chunks"


def summarize(checks: dict[str, dict[str, Any]], answers: Path) -> dict[str, Any]:
    recs = first_pass(answers)
    table = Counter((category(checks[q], recs[q]), outcome(recs[q])) for q in checks)
    same = [q for q in checks if sorted(checks[q]["run"]) == sorted(checks[q]["wide5"])]
    return {
        "questions": len(checks),
        "k5_equals_wide5": sum(c["k5"] == c["wide5"] for c in checks.values()),
        "run_equals_wide5": len(same),
        "run_equals_k5": sum(sorted(c["run"]) == sorted(c["k5"]) for c in checks.values()),
        "gold_in_run": sum(
            bool(set(recs[q]["gold_doc_paths"]) & set(c["run"])) for q, c in checks.items()
        ),
        "gold_in_wide5": sum(c["gold_in_wide5"] for c in checks.values()),
        "hit_at_5_wide": sum(c["gold_in_wide_top5_documents"] for c in checks.values()),
        "table": {
            cat: {o: table[(cat, o)] for o in ("correct", "incomplete", "refused")}
            for cat in CATEGORIES
        },
        "correct_when_run_equals_wide5": sum(outcome(recs[q]) == "correct" for q in same),
        "refused_when_run_equals_wide5": sum(outcome(recs[q]) == "refused" for q in same),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--answers", type=Path, required=True)
    ap.add_argument("--golden", type=Path, default=PROJECT_DIR / "evals" / "golden.jsonl")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not args.out.exists():
        args.out.write_text(json.dumps(collect(args.answers, args.golden), indent=1), "utf-8")
    print(json.dumps(summarize(json.loads(args.out.read_text("utf-8")), args.answers), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
