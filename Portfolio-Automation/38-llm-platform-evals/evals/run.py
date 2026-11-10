"""RAG evaluation runner (protocol: docs/EVALS.md).

Asks every golden question through Open WebUI with the `k8s-concepts` collection attached,
scores the answers with evals.metrics and writes a JSON report plus a per-answer JSONL log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import httpx

from evals import metrics

PROJECT_DIR = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_DIR / "corpus" / "markdown"
COLLECTION = "k8s-concepts"
SEP = "__"

SYSTEM_PROMPT = (
    "Answer only from the provided context. Cite every source you use inline in the format "
    "[source_id], using the source_id given in the context, e.g. [1]. Do not cite anything "
    "that is not in the context. If the context does not contain the answer, reply exactly: "
    f"{metrics.REFUSAL_SENTENCE}"
)
CITATION_RE = re.compile(r"\[([^\[\]\n]{1,200})\]")


def corpus_paths(corpus_dir: Path = CORPUS_DIR) -> set[str]:
    return {p.relative_to(corpus_dir).as_posix() for p in corpus_dir.rglob("*.md")}


def extract_citations(answer: str, sources: list[str]) -> list[str]:
    """Bracketed ids in the answer as corpus paths.

    `[3]` is the 3rd distinct document the server attached (`sources`); `[a__b.md]` is a name.
    A number with no matching source is kept verbatim so that it fails the validity check.
    """
    out: list[str] = []
    for token in CITATION_RE.findall(answer):
        token = token.strip()
        if token.isdigit():
            idx = int(token) - 1
            out.append(sources[idx] if 0 <= idx < len(sources) else token)
        elif token.endswith(".md"):
            out.append(token.replace(SEP, "/"))
        # other brackets (e.g. [x] or code) are not citations
    return out


class OpenWebUIClient:
    """The only place that talks HTTP."""

    def __init__(self, base_url: str, model: str, timeout_s: float, temperature: float, seed: int):
        self.model, self.temperature, self.seed = model, temperature, seed
        self.http = httpx.Client(base_url=base_url, timeout=timeout_s)
        resp = self.http.post(
            "/api/v1/auths/signin",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )
        resp.raise_for_status()
        self.http.headers["Authorization"] = "Bearer " + resp.json()["token"]
        kb = self.http.get("/api/v1/knowledge/")
        kb.raise_for_status()
        ids = [k["id"] for k in kb.json() if k.get("name") == COLLECTION]
        if not ids:
            raise RuntimeError(f"Collection {COLLECTION} not found; run scripts/ingest.py")
        self.kid = ids[0]

    def top_sources(self, question: str, n: int = 5) -> list[str]:
        """First n distinct documents of the retrieval ranking."""
        resp = self.http.post(
            "/api/v1/retrieval/query/collection",
            json={"collection_names": [self.kid], "query": question, "k": 4 * n},
        )
        resp.raise_for_status()
        names = [m["name"].replace(SEP, "/") for m in resp.json()["metadatas"][0]]
        return list(dict.fromkeys(names))[:n]

    def ask(self, question: str) -> tuple[str, list[str]]:
        """Return (answer, distinct source documents the server attached, in citation order)."""
        resp = self.http.post(
            "/api/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "stream": False,
                "temperature": self.temperature,
                "seed": self.seed,
                "files": [{"type": "collection", "id": self.kid}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"] or ""
        names: list[str] = []
        for src in data.get("sources") or []:
            for meta in src.get("metadata") or []:
                names.append(meta.get("name") or meta.get("source") or "")
        return answer, [n.replace(SEP, "/") for n in dict.fromkeys(names) if n]


def pass_metrics(records: list[dict[str, Any]], paths: set[str]) -> dict[str, float]:
    ans = [r for r in records if r["answerable"]]
    unans = [r for r in records if not r["answerable"]]
    out: dict[str, float] = {}
    if ans:
        out["hit_at_5"] = metrics.hit_at_5(
            [r["gold_doc_paths"] for r in ans], [r["top_sources"] for r in ans]
        )
        out["key_fact_correctness"] = metrics.key_fact_correctness(
            [r["answer"] for r in ans], [r["key_fact_regexes"] for r in ans]
        )
        out["false_refusal_rate"] = metrics.refusal_rate([r["answer"] for r in ans])
    if unans:
        out["refusal_rate"] = metrics.refusal_rate([r["answer"] for r in unans])
    out["citation_validity"] = metrics.citation_validity(
        [r["citations"] for r in records], [r["top_sources"] for r in records], paths
    )
    out["errors"] = float(sum("error" in r for r in records))  # failed or timed-out calls
    return out


def run(
    client: Any,
    items: list[dict[str, Any]],
    passes: int,
    answers_path: Path,
    paths: set[str],
) -> list[dict[str, float]]:
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    top_cache: dict[str, list[str]] = {}
    per_pass: list[dict[str, float]] = []
    with answers_path.open("a", encoding="utf-8") as log:
        for p in range(1, passes + 1):
            records: list[dict[str, Any]] = []
            for i, item in enumerate(items, 1):
                rec: dict[str, Any] = {
                    "pass": p,
                    "id": item["id"],
                    "answerable": item["answerable"],
                    "gold_doc_paths": item["gold_doc_paths"],
                    "key_fact_regexes": item["key_fact_regexes"],
                    "answer": "",
                    "top_sources": [],
                    "citations": [],
                }
                try:
                    if item["id"] not in top_cache:
                        top_cache[item["id"]] = client.top_sources(item["question"])
                    rec["top_sources"] = top_cache[item["id"]]
                    answer, attached = client.ask(item["question"])
                    rec["answer"] = answer
                    rec["citations"] = extract_citations(answer, attached)
                except Exception as exc:  # noqa: BLE001 - record and keep going
                    rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
                log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                log.flush()
                records.append(rec)
                flag = " ERROR" if "error" in rec else ""
                print(f"pass {p} [{i}/{len(items)}] {item['id']}{flag}", flush=True)
            per_pass.append(pass_metrics(records, paths))
    return per_pass


def build_report(
    per_pass: list[dict[str, float]], config: dict[str, Any], baseline: dict[str, Any] | None
) -> dict[str, Any]:
    names = sorted({n for m in per_pass for n in m})
    summary = {n: metrics.summarize([m[n] for m in per_pass if n in m]) for n in names}
    means = {n: s["mean"] for n, s in summary.items()}
    report: dict[str, Any] = {
        "config": config,
        "per_pass": per_pass,
        "summary": summary,
        "thresholds": metrics.THRESHOLDS,
        "threshold_pass": metrics.threshold_check(means),
    }
    if baseline is not None:
        base_means = {n: s["mean"] for n, s in baseline["summary"].items()}
        report["regression_pass"] = metrics.regression_check(means, base_means)
    return report


def print_table(report: dict[str, Any]) -> None:
    print(f"{'metric':24}{'mean':>7}{'min':>7}{'max':>7}{'thr':>7}  ok")
    for n, s in report["summary"].items():
        ok = report["threshold_pass"].get(n)
        thr = report["thresholds"].get(n, float("nan"))
        print(f"{n:24}{s['mean']:7.3f}{s['min']:7.3f}{s['max']:7.3f}{thr:7.2f}  {ok}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", type=Path, default=PROJECT_DIR / "evals" / "golden.jsonl")
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    ap.add_argument("--passes", type=int)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path, default=PROJECT_DIR / "results" / "evals.json")
    ap.add_argument("--answers", type=Path, default=PROJECT_DIR / "results" / "eval_answers.jsonl")
    ap.add_argument("--baseline", type=Path)
    args = ap.parse_args()

    passes = args.passes or (3 if args.split == "test" else 1)
    cfg = tomllib.loads((PROJECT_DIR / "evals" / "config.toml").read_text(encoding="utf-8"))["eval"]
    items = [
        json.loads(line)
        for line in args.golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    items = [i for i in items if i["split"] == args.split][: args.limit]
    if not items:
        print("No questions selected.", file=sys.stderr)
        return 1

    model = os.environ.get("EVAL_MODEL", "primary-model")
    config = {
        "model": model,
        "split": args.split,
        "passes": passes,
        "questions": len(items),
        "temperature": cfg["temperature"],
        "seed": cfg["seed"],
    }
    client = OpenWebUIClient(
        os.environ.get("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088"),
        model,
        float(os.environ.get("EVAL_TIMEOUT_S", "300")),
        cfg["temperature"],
        cfg["seed"],
    )
    per_pass = run(client, items, passes, args.answers, corpus_paths())
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    report = build_report(per_pass, config, baseline)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_table(report)
    if baseline is not None and not all(report["regression_pass"].values()):
        print("REGRESSION: " + ", ".join(k for k, v in report["regression_pass"].items() if not v))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
