"""Human review tooling: export review markdown and compute human precision score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def export_review(model_name: str, reports_dir: Path | None = None) -> Path:
    """Export review sheet from eval.json to review.md with an empty review column."""
    base_dir = Path(__file__).resolve().parent.parent
    target_dir = reports_dir or (base_dir / "reports" / model_name.replace(":", "-"))  # ":" is not valid in a Windows path
    eval_json_path = target_dir / "eval.json"

    if not eval_json_path.is_file():
        raise FileNotFoundError(
            f"Cannot export review: '{eval_json_path}' not found. Run runner first."
        )

    with open(eval_json_path, encoding="utf-8") as f:
        data = json.load(f)

    review_md_path = target_dir / "review.md"
    req_results = data.get("requirements_results", [])

    lines: list[str] = [
        f"# Human Review Sheet — Model: `{model_name}`",
        "",
        "- **Instructions:** Evaluate each generated test case and enter one of the following",
        "  into the `Review (OK/wrong/edit)` column:",
        "  - `OK`: Test case is valid, realistic, and covers the designated criteria.",
        "  - `wrong`: Test case is nonsensical, hallucinated, or unexecutable.",
        "  - `edit`: Test case has good intent but requires manual adjustment.",
        "- Leave the cell empty until reviewed.",
        "",
        "| Req ID | Case ID | Level | Title | Steps | Expected | Covers | Review (OK/wrong/edit) | Notes |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |",
    ]

    total_cases = 0
    for res in req_results:
        req_id = res.get("requirement_id", "")
        cases = res.get("test_cases", [])
        for tc in cases:
            total_cases += 1
            cid = tc.get("id", "")
            lvl = tc.get("level", "")
            title = tc.get("title", "").replace("|", "-")
            raw_steps = tc.get("steps", [])
            steps = "<br>".join(f"{idx+1}. {s.replace('|', '-')}" for idx, s in enumerate(raw_steps))
            expected = tc.get("expected", "").replace("|", "-")
            covers = ", ".join(tc.get("covers", []))

            # Column 8 is empty for human review
            lines.append(
                f"| `{req_id}` | `{cid}` | `{lvl}` | {title} | {steps} | {expected} | {covers} | | |"
            )

    with open(review_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return review_md_path


def parse_review_file(review_path: Path) -> dict[str, Any]:
    """Parse review.md and extract counts of OK, wrong, edit, and unreviewed cases."""
    if not review_path.is_file():
        raise FileNotFoundError(f"Review file not found: {review_path}")

    with open(review_path, encoding="utf-8") as f:
        lines = f.readlines()

    ok_count = 0
    wrong_count = 0
    edit_count = 0
    unreviewed_count = 0
    total_rows = 0

    for line in lines:
        line_str = line.strip()
        if not line_str.startswith("|") or line_str.startswith("| :---"):
            continue

        parts = [p.strip() for p in line_str.split("|")]
        # markdown table row split: ['', Req ID, Case ID, Level, Title, Steps, Expected, Covers, Review, Notes, '']
        if len(parts) < 10 or parts[1] == "Req ID":
            continue

        total_rows += 1
        review_val = parts[8].strip().lower()

        if review_val in ("ok", "okay", "pass"):
            ok_count += 1
        elif review_val in ("wrong", "fail", "incorrecto"):
            wrong_count += 1
        elif review_val in ("edit", "modificar", "ajustar"):
            edit_count += 1
        elif not review_val:
            unreviewed_count += 1
        else:
            # Unrecognized non-empty review label counts as wrong or unclassified
            wrong_count += 1

    return {
        "total_cases": total_rows,
        "unreviewed": unreviewed_count,
        "ok": ok_count,
        "wrong": wrong_count,
        "edit": edit_count,
        "total_reviewed": ok_count + wrong_count + edit_count,
    }


def score_review(model_name: str, reports_dir: Path | None = None) -> dict[str, Any] | None:
    """Compute human precision score if reviews have been filled; otherwise report no review."""
    base_dir = Path(__file__).resolve().parent.parent
    target_dir = reports_dir or (base_dir / "reports" / model_name.replace(":", "-"))  # ":" is not valid in a Windows path
    review_md_path = target_dir / "review.md"

    if not review_md_path.is_file():
        raise FileNotFoundError(f"Review sheet '{review_md_path}' does not exist.")

    counts = parse_review_file(review_md_path)
    total_reviewed = counts["total_reviewed"]

    if total_reviewed == 0:
        print(
            f"No completed reviews found in '{review_md_path}'. "
            f"All {counts['total_cases']} cases are pending human review. "
            f"Precision score cannot be computed without human evaluations."
        )
        return None

    precision = counts["ok"] / total_reviewed
    counts["human_precision"] = round(precision, 4)

    print(f"=== Human Review Scoring for Model: {model_name} ===")
    print(f"Total Cases: {counts['total_cases']}")
    print(f"Reviewed Cases: {total_reviewed} / {counts['total_cases']}")
    print(f"Unreviewed: {counts['unreviewed']}")
    print(f"  - OK: {counts['ok']} ({counts['ok'] / total_reviewed * 100:.1f}%)")
    print(f"  - Wrong: {counts['wrong']} ({counts['wrong'] / total_reviewed * 100:.1f}%)")
    print(f"  - Edit: {counts['edit']} ({counts['edit'] / total_reviewed * 100:.1f}%)")
    print(f"Human Precision: {precision * 100:.1f}% ({precision:.4f})")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Human review exporter and precision scorer.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_p = subparsers.add_parser("export", help="Export review.md from eval.json")
    export_p.add_argument("--model", type=str, default="stub", help="Model name in reports/")

    score_p = subparsers.add_parser("score", help="Score completed human review in review.md")
    score_p.add_argument("--model", type=str, default="stub", help="Model name in reports/")

    args = parser.parse_args()

    if args.command == "export":
        out = export_review(args.model)
        print(f"Review sheet successfully generated at: {out}")
    elif args.command == "score":
        score_review(args.model)


if __name__ == "__main__":
    main()
