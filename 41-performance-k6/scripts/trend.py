"""Script for compiling a historical performance trend markdown table from k6 summaries.

Scans a directory containing run subdirectories (each containing a load-summary.json)
and generates a markdown table ordered by most recent run first.
Standard library only.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("trend")


def load_summary(file_path: Path) -> dict[str, Any] | None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "metrics" in data:
                return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Skipping unreadable summary file %s: %s", file_path, exc)
    return None


def format_p95(metrics: dict[str, Any], key: str) -> str:
    metric = metrics.get(key)
    if metric and isinstance(metric, dict) and "p(95)" in metric:
        return f"{metric['p(95)']:.2f} ms"
    return "—"


def generate_trend_report(summaries_dir: Path) -> str:
    if not summaries_dir.is_dir():
        return f"Directory not found: {summaries_dir}\n"

    entries: list[tuple[str, Path]] = []
    for item in summaries_dir.iterdir():
        if item.is_dir():
            load_file = item / "load-summary.json"
            if load_file.is_file():
                entries.append((item.name, load_file))

    if not entries:
        return "No valid k6 summaries parsed.\n"

    # Order most recent first (by mtime descending, label as tiebreaker)
    entries.sort(key=lambda x: (x[1].stat().st_mtime, x[0]), reverse=True)

    rows: list[dict[str, Any]] = []

    for label, file_path in entries:
        data = load_summary(file_path)
        if not data:
            continue

        metrics = data.get("metrics", {})
        total_reqs = metrics.get("http_reqs", {}).get("count", 0)
        failed_metric = metrics.get("http_req_failed", {})
        fail_rate = failed_metric.get("value", 0.0) * 100.0

        p95_overall = format_p95(metrics, "http_req_duration")
        p95_wc = format_p95(metrics, "http_req_duration{endpoint:webhook_woocommerce}")
        p95_shopify = format_p95(metrics, "http_req_duration{endpoint:webhook_shopify}")
        p95_admin = format_p95(metrics, "http_req_duration{endpoint:admin_orders}")

        thresholds_breached = False
        for m in metrics.values():
            if isinstance(m, dict) and "thresholds" in m:
                for breached in m["thresholds"].values():
                    if breached is True:
                        thresholds_breached = True
                        break

        status = "❌ FAIL" if (thresholds_breached or fail_rate > 2.0) else "✅ PASS"

        rows.append(
            {
                "run": label,
                "reqs": total_reqs,
                "fail_rate": f"{fail_rate:.2f}%",
                "p95_overall": p95_overall,
                "p95_wc": p95_wc,
                "p95_shopify": p95_shopify,
                "p95_admin": p95_admin,
                "status": status,
            }
        )

    if not rows:
        return "No valid k6 summaries parsed.\n"

    lines: list[str] = [
        "### Historical Performance Trend",
        "",
        "| Run / Artifact | Total Reqs | Error Rate | Overall p95 | WooCommerce p95 | Shopify p95 | Admin Orders p95 | Status |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]

    for r in rows:
        lines.append(
            f"| `{r['run']}` | {r['reqs']} | {r['fail_rate']} | {r['p95_overall']} | {r['p95_wc']} | {r['p95_shopify']} | {r['p95_admin']} | {r['status']} |"
        )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Compile a historical trend table from multiple k6 summary JSON files."
    )
    parser.add_argument("directory", help="Directory containing run subdirectories")
    parser.add_argument(
        "-o", "--output", help="Optional path to write markdown table output", default=None
    )

    args = parser.parse_args()
    dir_path = Path(args.directory)

    report_md = generate_trend_report(dir_path)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report_md)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_md, encoding="utf-8")


if __name__ == "__main__":
    main()
