"""Benchmark runner comparing Selenium 4 and Playwright test suites.

Only Python standard library modules are used (argparse, subprocess,
xml.etree.ElementTree, json, statistics, pathlib, sys).
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import statistics
import subprocess
import sys
import xml.etree.ElementTree as ET


def count_loc(dir_path: str | Path) -> dict[str, int]:
    """Count total and code lines (excluding comments and blank lines) in Python files."""
    path = Path(dir_path)
    total_lines = 0
    code_lines = 0
    file_count = 0

    for py_file in path.rglob("*.py"):
        if "__pycache__" in py_file.parts or ".pytest_cache" in py_file.parts:
            continue
        file_count += 1
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                for line in f:
                    total_lines += 1
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        code_lines += 1
        except (OSError, UnicodeDecodeError):
            continue

    return {
        "files": file_count,
        "total_lines": total_lines,
        "code_lines": code_lines,
    }


def parse_junit_xml(xml_source: str | Path) -> dict:
    """Parse a JUnit XML file or string and extract suite time and testcase results."""
    if isinstance(xml_source, Path) or (
        isinstance(xml_source, str) and not xml_source.strip().startswith("<")
    ):
        tree = ET.parse(xml_source)
        root = tree.getroot()
    else:
        root = ET.fromstring(xml_source)

    if root.tag == "testsuite":
        suite_time = float(root.attrib.get("time", 0.0))
    else:
        first_suite = root.find("testsuite")
        suite_time = float(first_suite.attrib.get("time", 0.0)) if first_suite is not None else 0.0

    testcases: list[dict] = []
    for tc in root.iter("testcase"):
        raw_name = tc.attrib.get("name", "")
        # Clean parameter suffixes like [chromium] or [channel=msedge]
        clean_name = raw_name.split("[")[0]
        tc_time = float(tc.attrib.get("time", 0.0))
        fail_node = tc.find("failure")
        err_node = tc.find("error")
        failed = fail_node is not None or err_node is not None
        failure_msg = ""
        if failed:
            elem = fail_node if fail_node is not None else err_node
            if elem is not None:
                failure_msg = elem.attrib.get("message") or (elem.text or "").strip()

        testcases.append({
            "name": clean_name,
            "raw_name": raw_name,
            "classname": tc.attrib.get("classname", ""),
            "time": tc_time,
            "failed": failed,
            "failure_message": failure_msg,
        })

    # If suite_time was not on root, sum individual testcase times
    if suite_time <= 0.0 and testcases:
        suite_time = sum(tc["time"] for tc in testcases)

    return {
        "suite_time": suite_time,
        "testcases": testcases,
    }


def percentile_95(values: list[float]) -> float:
    """Calculate the 95th percentile using linear interpolation."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * 0.95
    idx = int(k)
    frac = k - idx
    if idx + 1 < len(sorted_vals):
        return sorted_vals[idx] + frac * (sorted_vals[idx + 1] - sorted_vals[idx])
    return sorted_vals[-1]


def aggregate_suite_metrics(runs: list[dict], suite_loc: dict[str, int]) -> dict:
    """Aggregate metrics across multiple runs for a single suite."""
    if not runs:
        return {
            "runs": 0,
            "loc": suite_loc,
            "median_duration_s": 0.0,
            "p95_duration_s": 0.0,
            "scenarios": {},
        }

    suite_durations = [r["suite_time"] for r in runs]
    median_duration = statistics.median(suite_durations)
    p95_duration = percentile_95(suite_durations)

    # Collect all unique scenario names
    scenario_names: list[str] = []
    for r in runs:
        for tc in r["testcases"]:
            if tc["name"] not in scenario_names:
                scenario_names.append(tc["name"])

    scenario_metrics: dict[str, dict] = {}
    for name in scenario_names:
        times: list[float] = []
        failures = 0
        total_runs = 0
        for r in runs:
            matches = [tc for tc in r["testcases"] if tc["name"] == name]
            for tc in matches:
                total_runs += 1
                times.append(tc["time"])
                if tc["failed"]:
                    failures += 1

        fail_rate = (failures / total_runs) if total_runs > 0 else 0.0
        med_time = statistics.median(times) if times else 0.0
        p95_time = percentile_95(times) if times else 0.0

        scenario_metrics[name] = {
            "total_executions": total_runs,
            "failures": failures,
            "failure_rate": round(fail_rate, 4),
            "median_duration_s": round(med_time, 4),
            "p95_duration_s": round(p95_time, 4),
        }

    return {
        "runs": len(runs),
        "loc": suite_loc,
        "median_duration_s": round(median_duration, 4),
        "p95_duration_s": round(p95_duration, 4),
        "scenarios": scenario_metrics,
    }


def execute_suite_run(suite_dir: Path, xml_path: Path) -> dict:
    """Run pytest once for a suite, outputting to a JUnit XML file."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(suite_dir),
        f"--junitxml={xml_path}",
        "-q",
    ]
    # We do not fail-fast on non-zero exit code: failures are measured metrics
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=suite_dir.parent,
        check=False,
    )
    if not xml_path.exists():
        raise RuntimeError(
            f"Pytest failed to create XML report at {xml_path}.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return parse_junit_xml(xml_path)


def generate_benchmark_markdown(data: dict) -> str:
    """Generate Markdown report from benchmark aggregation data."""
    meta = data["metadata"]
    legacy = data["suites"]["legacy_selenium"]
    migrated = data["suites"]["migrated_playwright"]

    leg_med = legacy["median_duration_s"]
    mig_med = migrated["median_duration_s"]
    speedup = f"{(leg_med / mig_med):.2f}x" if mig_med > 0 else "N/A"

    leg_code_lines = legacy["loc"]["code_lines"]
    mig_code_lines = migrated["loc"]["code_lines"]
    loc_delta = (
        f"{((mig_code_lines - leg_code_lines) / leg_code_lines * 100):+.1f}%"
        if leg_code_lines > 0
        else "N/A"
    )

    lines = [
        "# Benchmark Report: Selenium 4 vs Playwright Migration",
        "",
        f"- **Timestamp**: {meta['timestamp']}",
        f"- **Repetitions per Suite**: {meta['runs']}",
        f"- **Python Interpreter**: {meta['python_version']}",
        f"- **Browser**: Microsoft Edge (headless)",
        "",
        "## 1. Suite-Level Summary",
        "",
        "| Metric | Legacy Selenium 4 | Migrated Playwright | Delta / Comparison |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Lines of Code (code lines)** | {leg_code_lines} | {mig_code_lines} | {loc_delta} |",
        f"| **Total Lines (with comments)** | {legacy['loc']['total_lines']} | {migrated['loc']['total_lines']} | - |",
        f"| **Python Files** | {legacy['loc']['files']} | {migrated['loc']['files']} | - |",
        f"| **Median Suite Duration** | {leg_med:.3f} s | {mig_med:.3f} s | **{speedup} faster** |",
        f"| **P95 Suite Duration** | {legacy['p95_duration_s']:.3f} s | {migrated['p95_duration_s']:.3f} s | - |",
        "",
        "## 2. Per-Scenario Failure Rate & Durations",
        "",
        "| Scenario | Selenium Fail Rate | Selenium Median | Playwright Fail Rate | Playwright Median | Speedup |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    all_scenarios = sorted(
        set(list(legacy["scenarios"].keys()) + list(migrated["scenarios"].keys()))
    )
    for sc in all_scenarios:
        leg_sc = legacy["scenarios"].get(sc, {})
        mig_sc = migrated["scenarios"].get(sc, {})

        leg_fr = f"{leg_sc.get('failure_rate', 0.0) * 100:.1f}% ({leg_sc.get('failures', 0)}/{leg_sc.get('total_executions', meta['runs'])})"
        mig_fr = f"{mig_sc.get('failure_rate', 0.0) * 100:.1f}% ({mig_sc.get('failures', 0)}/{mig_sc.get('total_executions', meta['runs'])})"

        leg_time = leg_sc.get("median_duration_s", 0.0)
        mig_time = mig_sc.get("median_duration_s", 0.0)
        sc_speedup = f"{(leg_time / mig_time):.2f}x" if mig_time > 0 and leg_time > 0 else "N/A"

        lines.append(
            f"| `{sc}` | {leg_fr} | {leg_time:.3f} s | {mig_fr} | {mig_time:.3f} s | {sc_speedup} |"
        )

    lines.extend([
        "",
        "## 3. Reading the numbers",
        "",
        f"- Suite duration: Playwright is **{speedup}** relative to Selenium 4 on the same 8 scenarios.",
        f"- Code size: **{loc_delta}** executable lines after the migration, same Page Object structure.",
        "- The Selenium suite starts one Edge process per test; the Playwright suite starts Edge once and "
        "opens a fresh context per test. Both isolate tests, and that difference is part of the speedup.",
        "- A failure rate of 0 over a few runs does not prove a suite is stable; raise --runs to look for "
        "intermittent failures.",
    ])

    return "\n".join(lines) + "\n"


def run_benchmark(
    runs: int = 10,
    project_dir: Path | None = None,
    output_dir: Path | None = None,
) -> tuple[dict, str]:
    """Execute the full benchmark suite N times and generate JSON and Markdown reports."""
    if project_dir is None:
        project_dir = Path(__file__).resolve().parent.parent

    if output_dir is None:
        output_dir = project_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    temp_xml_dir = output_dir / "xml_runs"
    temp_xml_dir.mkdir(parents=True, exist_ok=True)

    legacy_dir = project_dir / "legacy_selenium"
    migrated_dir = project_dir / "migrated_playwright"

    legacy_loc = count_loc(legacy_dir)
    migrated_loc = count_loc(migrated_dir)

    legacy_runs: list[dict] = []
    migrated_runs: list[dict] = []

    print(f"[*] Starting benchmark with {runs} runs per suite...")

    # Run legacy selenium suite
    print(f"\n[1/2] Running Selenium 4 suite ({runs} iterations)...")
    for i in range(1, runs + 1):
        xml_file = temp_xml_dir / f"selenium_run_{i}.xml"
        print(f"  -> Run {i}/{runs}...", end="", flush=True)
        run_data = execute_suite_run(legacy_dir, xml_file)
        legacy_runs.append(run_data)
        failed_count = sum(1 for tc in run_data["testcases"] if tc["failed"])
        print(f" done in {run_data['suite_time']:.2f}s (failures: {failed_count})")

    # Run migrated playwright suite
    print(f"\n[2/2] Running Playwright suite ({runs} iterations)...")
    for i in range(1, runs + 1):
        xml_file = temp_xml_dir / f"playwright_run_{i}.xml"
        print(f"  -> Run {i}/{runs}...", end="", flush=True)
        run_data = execute_suite_run(migrated_dir, xml_file)
        migrated_runs.append(run_data)
        failed_count = sum(1 for tc in run_data["testcases"] if tc["failed"])
        print(f" done in {run_data['suite_time']:.2f}s (failures: {failed_count})")

    legacy_metrics = aggregate_suite_metrics(legacy_runs, legacy_loc)
    migrated_metrics = aggregate_suite_metrics(migrated_runs, migrated_loc)

    data = {
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "runs": runs,
            "python_version": sys.version.split()[0],
        },
        "suites": {
            "legacy_selenium": legacy_metrics,
            "migrated_playwright": migrated_metrics,
        },
    }

    # Write results/benchmark.json
    json_path = output_dir / "benchmark.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Write results/benchmark.md
    md_content = generate_benchmark_markdown(data)
    md_path = output_dir / "benchmark.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n[+] Benchmark successfully written to:")
    print(f"    - JSON: {json_path}")
    print(f"    - MD:   {md_path}")

    return data, md_content


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run benchmark comparing Selenium 4 and Playwright test suites."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of repeated runs per test suite (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for benchmark reports (default: results/)",
    )
    args = parser.parse_args()

    run_benchmark(runs=args.runs, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
