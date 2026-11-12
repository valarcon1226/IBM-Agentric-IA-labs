"""Evaluation runner: executes generator over a dataset split and records reports."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from app.generator import GenerationResult, TestCaseGenerator
from app.llm import BaseLLM, OpenAILLM, StubLLM
from app.models import Requirement, TestCase
from evals import metrics


def load_config(config_path: Path) -> dict[str, Any]:
    """Load pre-registered thresholds and comparisons from TOML configuration."""
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_requirements(golden_dir: Path, split: str = "dev") -> list[Requirement]:
    """Load requirement JSON files belonging to the chosen split."""
    requirements: list[Requirement] = []
    for file_path in sorted(golden_dir.glob("*.json")):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            req = Requirement.model_validate(data)
            if split == "all" or req.split == split:
                requirements.append(req)
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to load {file_path}: {e}\n")
    return requirements


def evaluate_threshold(score: float, threshold: float, operator: str) -> bool:
    """Compare a metric score against a pre-registered threshold."""
    if operator == ">=":
        return score >= threshold
    if operator == "<=":
        return score <= threshold
    if operator == "==":
        return score == threshold
    if operator == ">":
        return score > threshold
    if operator == "<":
        return score < threshold
    raise ValueError(f"Unsupported comparison operator: {operator}")


def run_evaluation(
    model_name: str,
    split: str = "dev",
    golden_dir_path: Path | None = None,
    config_path: Path | None = None,
    output_dir_path: Path | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    custom_llm: BaseLLM | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    """Execute the full evaluation pipeline and write reports/eval.json & eval.md."""
    base_dir = Path(__file__).resolve().parent.parent
    golden_dir = golden_dir_path or (base_dir / "evals" / "golden")
    cfg_file = config_path or (base_dir / "evals" / "config.toml")
    reports_dir = output_dir_path or (base_dir / "reports" / model_name.replace(":", "-"))  # ":" is not valid in a Windows path
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(cfg_file)
    thresholds = config.get("thresholds", {})
    comparisons = config.get("comparisons", {})

    requirements = load_requirements(golden_dir, split=split)
    if not requirements:
        raise ValueError(f"No requirements found in {golden_dir} for split '{split}'")

    if custom_llm is not None:
        llm: BaseLLM = custom_llm
    elif model_name.lower() == "stub":
        llm = StubLLM()
    else:
        llm = OpenAILLM(base_url=base_url, model=model_name, timeout=timeout)

    generator = TestCaseGenerator()
    results: list[GenerationResult] = []
    test_cases_by_req: dict[str, list[TestCase]] = {}

    for req in requirements:
        try:
            gen_res = generator.generate(req, llm)
        except Exception as e:
            gen_res = GenerationResult(
                requirement_id=req.id,
                requirement_title=req.title,
                test_cases=[],
                raw_response="",
                valid_on_first_try=False,
                retries_used=1,
                error=f"Uncaught exception: {e}",
            )
        results.append(gen_res)
        test_cases_by_req[req.id] = gen_res.test_cases

    # Calculate metrics deterministically
    schema_val = metrics.schema_valid_rate(results)
    decl_cov = metrics.declared_coverage(requirements, test_cases_by_req)
    ver_cov = metrics.verified_coverage(requirements, test_cases_by_req)
    halluc = metrics.hallucinated_refs(requirements, test_cases_by_req)
    dupl_rate = metrics.duplicate_rate(requirements, test_cases_by_req)
    neg_pres = metrics.negative_presence(requirements, test_cases_by_req)

    computed_metrics = {
        "schema_valid_rate": {
            "score": round(schema_val, 4),
            "threshold": thresholds.get("schema_valid_rate", 0.90),
            "operator": comparisons.get("schema_valid_rate", ">="),
            "passed": evaluate_threshold(
                schema_val,
                thresholds.get("schema_valid_rate", 0.90),
                comparisons.get("schema_valid_rate", ">="),
            ),
        },
        "declared_coverage": {
            "score": round(decl_cov, 4),
            "threshold": thresholds.get("declared_coverage", 0.70),
            "operator": comparisons.get("declared_coverage", ">="),
            "passed": evaluate_threshold(
                decl_cov,
                thresholds.get("declared_coverage", 0.70),
                comparisons.get("declared_coverage", ">="),
            ),
        },
        "verified_coverage": {
            "score": round(ver_cov, 4),
            "threshold": thresholds.get("verified_coverage", 0.70),
            "operator": comparisons.get("verified_coverage", ">="),
            "passed": evaluate_threshold(
                ver_cov,
                thresholds.get("verified_coverage", 0.70),
                comparisons.get("verified_coverage", ">="),
            ),
        },
        "hallucinated_refs": {
            "score": round(halluc, 4),
            "threshold": thresholds.get("hallucinated_refs", 0.02),
            "operator": comparisons.get("hallucinated_refs", "<="),
            "passed": evaluate_threshold(
                halluc,
                thresholds.get("hallucinated_refs", 0.02),
                comparisons.get("hallucinated_refs", "<="),
            ),
        },
        "duplicate_rate": {
            "score": round(dupl_rate, 4),
            "threshold": thresholds.get("duplicate_rate", 0.10),
            "operator": comparisons.get("duplicate_rate", "<="),
            "passed": evaluate_threshold(
                dupl_rate,
                thresholds.get("duplicate_rate", 0.10),
                comparisons.get("duplicate_rate", "<="),
            ),
        },
        "negative_presence": {
            "score": round(neg_pres, 4),
            "threshold": thresholds.get("negative_presence", 1.0),
            "operator": comparisons.get("negative_presence", ">="),
            "passed": evaluate_threshold(
                neg_pres,
                thresholds.get("negative_presence", 1.0),
                comparisons.get("negative_presence", ">="),
            ),
        },
    }

    now_iso = datetime.now(UTC).isoformat()
    total_cases = sum(len(tc_list) for tc_list in test_cases_by_req.values())

    report_payload = {
        "model": model_name,
        "split": split,
        "timestamp_utc": now_iso,
        "total_requirements": len(requirements),
        "total_test_cases": total_cases,
        "metrics": computed_metrics,
        "requirements_results": [
            {
                "requirement_id": r.requirement_id,
                "requirement_title": r.requirement_title,
                "valid_on_first_try": r.valid_on_first_try,
                "retries_used": r.retries_used,
                "error": r.error,
                "raw_response": r.raw_response,
                "test_cases": [tc.model_dump() for tc in r.test_cases],
            }
            for r in results
        ],
    }

    json_path = reports_dir / "eval.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2, ensure_ascii=False)

    md_path = reports_dir / "eval.md"
    md_content = build_markdown_report(report_payload, requirements, test_cases_by_req)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return report_payload, json_path, md_path


def build_markdown_report(
    data: dict[str, Any],
    requirements: list[Requirement],
    test_cases_by_req: dict[str, list[TestCase]],
) -> str:
    """Generate professional evaluation markdown report."""
    metrics_info = data["metrics"]
    all_passed = all(m["passed"] for m in metrics_info.values())
    status_banner = "✅ ALL THRESHOLDS PASSED" if all_passed else "⚠️ THRESHOLD BREACH DETECTED"

    lines: list[str] = [
        f"# Test Case Generator Evaluation Report — `{data['model']}`",
        "",
        f"- **Model Evaluated:** `{data['model']}`",
        f"- **Split:** `{data['split']}`",
        f"- **Timestamp (UTC):** `{data['timestamp_utc']}`",
        f"- **Total Requirements:** {data['total_requirements']}",
        f"- **Total Generated Test Cases:** {data['total_test_cases']}",
        f"- **Overall Evaluation Status:** **{status_banner}**",
        "",
        "## Summary Metrics vs. Pre-Registered Thresholds",
        "",
        "| Metric | Measured Score | Pre-Registered Threshold | Status |",
        "| :--- | :---: | :---: | :---: |",
    ]

    metric_labels = {
        "schema_valid_rate": "Schema Valid Rate (1st Try)",
        "declared_coverage": "Declared Criteria Coverage",
        "verified_coverage": "Verified Regex Coverage",
        "hallucinated_refs": "Hallucinated Criterion Refs",
        "duplicate_rate": "Duplicate Case Rate (difflib ≥ 0.9)",
        "negative_presence": "Negative/Edge Test Case Presence",
    }

    for key, label in metric_labels.items():
        if key in metrics_info:
            item = metrics_info[key]
            op = item["operator"]
            thresh = item["threshold"]
            score = item["score"]
            status_badge = "✅ PASS" if item["passed"] else "❌ FAIL"

            # Format percentages vs proportions
            if key in ("hallucinated_refs", "duplicate_rate"):
                score_str = f"{score * 100:.1f}% ({score:.4f})"
                thresh_str = f"{op} {thresh * 100:.1f}%"
            else:
                score_str = f"{score * 100:.1f}% ({score:.4f})"
                thresh_str = f"{op} {thresh * 100:.1f}%"

            lines.append(f"| **{label}** | {score_str} | {thresh_str} | {status_badge} |")

    lines.extend([
        "",
        "## Per-Requirement Breakdown",
        "",
        "| Requirement ID | Title | Cases | 1st Try Valid? | Level Distribution |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ])

    for res in data["requirements_results"]:
        req_id = res["requirement_id"]
        title = res["requirement_title"]
        cases = res["test_cases"]
        valid_1st = "Yes" if res["valid_on_first_try"] else f"No ({res['retries_used']} retry)"

        # Count levels
        levels: dict[str, int] = {}
        for tc in cases:
            lvl = tc.get("level", "unknown")
            levels[lvl] = levels.get(lvl, 0) + 1
        lvl_str = ", ".join(f"{count} {lvl}" for lvl, count in sorted(levels.items())) or "0 cases"

        lines.append(f"| `{req_id}` | {title} | {len(cases)} | {valid_1st} | {lvl_str} |")

    lines.extend([
        "",
        "## Notes on Evaluation Rigor",
        "",
        "- **Harness Self-Check:** When running with `--model stub`, this suite verifies that the",
        "  evaluator, acceptance criteria regular expressions, and parsing logic agree.",
        "- **Goalpost Protection:** Thresholds were committed in `evals/config.toml` prior to",
        "  evaluating production local models.",
    ])

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run test case generator evaluation across golden requirements split."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="stub",
        help="Model to evaluate (e.g. 'stub' or Ollama model name like 'llama3.2')",
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["dev", "test", "all"],
        default="dev",
        help="Dataset split to evaluate ('dev', 'test', or 'all')",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Optional base URL for OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Optional request timeout in seconds",
    )
    args = parser.parse_args()

    payload, json_path, md_path = run_evaluation(
        model_name=args.model,
        split=args.split,
        base_url=args.base_url,
        timeout=args.timeout,
    )

    print(f"Evaluation complete for model '{args.model}' on split '{args.split}'.")
    print(f"JSON Report: {json_path}")
    print(f"Markdown Report: {md_path}")
    print("\nMetrics Summary:")
    for k, v in payload["metrics"].items():
        status = "PASS" if v["passed"] else "FAIL"
        print(f"  - {k}: {v['score']} (threshold {v['operator']} {v['threshold']}) -> {status}")


if __name__ == "__main__":
    main()
