"""Script for comparing k6 test summary against a baseline.

Exits with code 1 if p95 of any endpoint regresses by more than the tolerance (25% by default) or if error rate increases.
Outputs a clean Markdown table summarizing the comparison.
Standard library only.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_summary(file_path: Path) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_metrics(
    current_data: dict[str, Any], baseline_data: dict[str, Any], tolerance_pct: float = 25.0
) -> tuple[bool, str]:
    curr_metrics = current_data.get("metrics", {})
    base_metrics = baseline_data.get("metrics", {})

    failed = False
    reasons: list[str] = []

    # 1. Compare p95 durations (overall and per-endpoint)
    duration_keys = sorted(
        {
            k
            for k in list(curr_metrics.keys()) + list(base_metrics.keys())
            if k.startswith("http_req_duration")
            and not k.endswith("expected_response:true}")
            and not k.endswith("expected_response:false}")
        }
    )

    p95_rows: list[dict[str, Any]] = []

    for k in duration_keys:
        curr_p95 = curr_metrics.get(k, {}).get("p(95)", 0.0)
        base_p95 = base_metrics.get(k, {}).get("p(95)", 0.0)

        # Clean display label
        if "endpoint:" in k:
            endpoint_name = k.split("endpoint:")[1].rstrip("}")
            label = f"`{endpoint_name}`"
        else:
            label = "`http_req_duration` (overall)"

        if base_p95 > 0:
            delta_pct = ((curr_p95 - base_p95) / base_p95) * 100.0
        else:
            delta_pct = 0.0

        is_regressed = base_p95 > 0 and curr_p95 > base_p95 * (1 + tolerance_pct / 100)
        if is_regressed:
            failed = True
            reasons.append(
                f"{label} p95 regressed by {delta_pct:+.2f}% (base: {base_p95:.2f}ms, curr: {curr_p95:.2f}ms)"
            )
            status = "**FAIL**"
        else:
            status = "PASS"

        p95_rows.append(
            {
                "label": label,
                "base_p95": base_p95,
                "curr_p95": curr_p95,
                "delta_pct": delta_pct,
                "status": status,
            }
        )

    # 2. Compare error rate (http_req_failed)
    curr_failed = curr_metrics.get("http_req_failed", {})
    base_failed = base_metrics.get("http_req_failed", {})

    curr_fail_rate = curr_failed.get("value", 0.0)
    base_fail_rate = base_failed.get("value", 0.0)

    # Check if error rate increased (with small float tolerance)
    error_increased = curr_fail_rate > (base_fail_rate + 1e-6)
    if error_increased:
        failed = True
        reasons.append(
            f"Error rate increased from {base_fail_rate * 100:.2f}% to {curr_fail_rate * 100:.2f}%"
        )
        error_status = "**FAIL**"
    else:
        error_status = "PASS"

    # Build Markdown Report
    lines: list[str] = [
        "### Performance Regression Gate Comparison",
        "",
        "#### Response Time (p95)",
        "",
        "| Metric / Endpoint | Baseline p95 (ms) | Current p95 (ms) | Delta (%) | Threshold | Status |",
        "|---|---:|---:|---:|---:|:---:|",
    ]

    for row in p95_rows:
        delta_str = f"{row['delta_pct']:+.2f}%" if row['base_p95'] > 0 else "N/A"
        lines.append(
            f"| {row['label']} | {row['base_p95']:.2f} | {row['curr_p95']:.2f} | {delta_str} | ≤ +{tolerance_pct:.1f}% | {row['status']} |"
        )

    lines.extend(
        [
            "",
            "#### Reliability / Error Rate",
            "",
            "| Metric | Baseline Rate | Current Rate | Delta | Threshold | Status |",
            "|---|---:|---:|---:|---:|:---:|",
            f"| `http_req_failed` | {base_fail_rate * 100:.2f}% | {curr_fail_rate * 100:.2f}% | {(curr_fail_rate - base_fail_rate) * 100:+.2f}% | ≤ baseline | {error_status} |",
            "",
            "#### Overall Gate Status",
            "",
            f"**Verdict:** {'❌ FAILED' if failed else '✅ PASSED'}",
        ]
    )

    if failed:
        lines.extend(["", "**Failures detected:**"])
        for r in reasons:
            lines.append(f"- ❌ {r}")

    markdown_output = "\n".join(lines) + "\n"
    return failed, markdown_output


def main():
    parser = argparse.ArgumentParser(
        description="Compare k6 summary against baseline and enforce performance regression gates."
    )
    parser.add_argument("summary", help="Path to current k6 summary JSON file")
    parser.add_argument("baseline", help="Path to baseline k6 summary JSON file")
    parser.add_argument(
        "-o", "--output", help="Optional path to write markdown table output", default=None
    )

    parser.add_argument(
        "--tolerance",
        type=float,
        default=25.0,
        help="Allowed p95 increase over the baseline, in percent (default 25)",
    )

    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # the report has non-ASCII symbols

    summary_path = Path(args.summary)
    baseline_path = Path(args.baseline)

    if not summary_path.is_file():
        print(f"Error: summary file not found: {summary_path}", file=sys.stderr)
        sys.exit(2)

    if not baseline_path.is_file():
        print(f"Error: baseline file not found: {baseline_path}", file=sys.stderr)
        sys.exit(2)

    curr_data = parse_summary(summary_path)
    base_data = parse_summary(baseline_path)

    failed, md_report = compare_metrics(curr_data, base_data, args.tolerance)

    print(md_report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_report, encoding="utf-8")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
