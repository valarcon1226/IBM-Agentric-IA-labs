"""Unit tests for compare.py and trend.py using sample k6 summaries."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from scripts.compare import compare_metrics
from scripts.trend import generate_trend_report


def make_summary(
    p95_overall: float,
    p95_wc: float,
    p95_shopify: float,
    p95_admin: float,
    fail_rate: float = 0.0,
    total_reqs: int = 100,
) -> dict:
    return {
        "metrics": {
            "http_req_duration": {"p(95)": p95_overall, "avg": p95_overall * 0.7},
            "http_req_duration{endpoint:webhook_woocommerce}": {
                "p(95)": p95_wc,
                "avg": p95_wc * 0.7,
            },
            "http_req_duration{endpoint:webhook_shopify}": {
                "p(95)": p95_shopify,
                "avg": p95_shopify * 0.7,
            },
            "http_req_duration{endpoint:admin_orders}": {
                "p(95)": p95_admin,
                "avg": p95_admin * 0.7,
            },
            "http_req_failed": {"value": fail_rate, "passes": 0, "fails": total_reqs},
            "http_reqs": {"count": total_reqs, "rate": 10.0},
        }
    }


def test_compare_pass():
    baseline = make_summary(
        p95_overall=100.0, p95_wc=120.0, p95_shopify=110.0, p95_admin=90.0, fail_rate=0.0
    )
    # +10% latency, well below +25% threshold
    current = make_summary(
        p95_overall=110.0, p95_wc=125.0, p95_shopify=115.0, p95_admin=95.0, fail_rate=0.0
    )

    failed, report = compare_metrics(current, baseline)
    assert not failed
    assert "✅ PASSED" in report
    assert "PASS" in report


def test_compare_p95_regression_fail():
    baseline = make_summary(p95_overall=100.0, p95_wc=100.0, p95_shopify=100.0, p95_admin=100.0)
    # WooCommerce regressed by +30% (> 25% threshold)
    current = make_summary(p95_overall=105.0, p95_wc=130.0, p95_shopify=102.0, p95_admin=98.0)

    failed, report = compare_metrics(current, baseline)
    assert failed
    assert "❌ FAILED" in report
    assert "regressed by +30.00%" in report


def test_compare_error_rate_fail():
    baseline = make_summary(
        p95_overall=100.0, p95_wc=100.0, p95_shopify=100.0, p95_admin=100.0, fail_rate=0.0
    )
    # Error rate increased to 3%
    current = make_summary(
        p95_overall=95.0, p95_wc=95.0, p95_shopify=95.0, p95_admin=95.0, fail_rate=0.03
    )

    failed, report = compare_metrics(current, baseline)
    assert failed
    assert "❌ FAILED" in report
    assert "Error rate increased" in report


def test_compare_cli_invocation(tmp_path: Path):
    base_file = tmp_path / "baseline.json"
    curr_pass_file = tmp_path / "curr_pass.json"
    curr_fail_file = tmp_path / "curr_fail.json"

    base_data = make_summary(100.0, 100.0, 100.0, 100.0, fail_rate=0.0)
    pass_data = make_summary(110.0, 110.0, 110.0, 110.0, fail_rate=0.0)
    fail_data = make_summary(150.0, 150.0, 150.0, 150.0, fail_rate=0.0)

    base_file.write_text(json.dumps(base_data), encoding="utf-8")
    curr_pass_file.write_text(json.dumps(pass_data), encoding="utf-8")
    curr_fail_file.write_text(json.dumps(fail_data), encoding="utf-8")

    compare_py = Path(__file__).resolve().parent.parent / "scripts" / "compare.py"

    # Test passing invocation (exit code 0)
    res_pass = subprocess.run(
        [sys.executable, str(compare_py), str(curr_pass_file), str(base_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert res_pass.returncode == 0
    assert "✅ PASSED" in res_pass.stdout

    # Test failing invocation (exit code 1)
    res_fail = subprocess.run(
        [sys.executable, str(compare_py), str(curr_fail_file), str(base_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert res_fail.returncode == 1
    assert "❌ FAILED" in res_fail.stdout


def test_trend_report_generation(tmp_path: Path):
    run1_dir = tmp_path / "run-1"
    run2_dir = tmp_path / "run-2"
    run1_dir.mkdir()
    run2_dir.mkdir()

    # Ignored file in root or another scenario file
    (tmp_path / "smoke-summary.json").write_text("{}", encoding="utf-8")
    (run1_dir / "smoke-summary.json").write_text("{}", encoding="utf-8")

    f1 = run1_dir / "load-summary.json"
    f2 = run2_dir / "load-summary.json"

    f1.write_text(
        json.dumps(make_summary(120.0, 130.0, 125.0, 110.0, fail_rate=0.0, total_reqs=500)),
        encoding="utf-8",
    )
    f2.write_text(
        json.dumps(make_summary(115.0, 122.0, 118.0, 105.0, fail_rate=0.0, total_reqs=600)),
        encoding="utf-8",
    )

    # Set timestamps so run-2 is more recent than run-1
    t = time.time()
    os.utime(f1, (t - 100, t - 100))
    os.utime(f2, (t, t))

    report = generate_trend_report(tmp_path)
    assert "### Historical Performance Trend" in report
    assert "`run-1`" in report
    assert "`run-2`" in report
    assert "smoke" not in report
    assert "500" in report
    assert "600" in report

    # Ordered most recent first: run-2 appears before run-1
    assert report.index("`run-2`") < report.index("`run-1`")


def test_trend_cli_invocation(tmp_path: Path):
    run_dir = tmp_path / "current"
    run_dir.mkdir()
    (run_dir / "load-summary.json").write_text(
        json.dumps(make_summary(100.0, 100.0, 100.0, 100.0)), encoding="utf-8"
    )

    trend_py = Path(__file__).resolve().parent.parent / "scripts" / "trend.py"
    res = subprocess.run(
        [sys.executable, str(trend_py), str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 0
    assert "`current`" in res.stdout
