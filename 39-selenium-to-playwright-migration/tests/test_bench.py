"""Tests for benchmark parser, metric calculations, and report generator."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from bench.run import (
    aggregate_suite_metrics,
    count_loc,
    generate_benchmark_markdown,
    parse_junit_xml,
    percentile_95,
)

SAMPLE_PASSING_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="2" errors="0" failures="0" skipped="0" time="4.500">
    <testcase classname="legacy_selenium.test_scenarios" name="test_login_valid" time="2.100" />
    <testcase classname="legacy_selenium.test_scenarios" name="test_search_with_results" time="1.400" />
</testsuite>
"""

SAMPLE_MIXED_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="3" errors="1" failures="1" skipped="0" time="6.200">
    <testcase classname="migrated_playwright.test_scenarios" name="test_login_valid[msedge]" time="1.200" />
    <testcase classname="migrated_playwright.test_scenarios" name="test_search_with_results[msedge]" time="1.000">
        <failure message="AssertionError: assert False">Traceback...</failure>
    </testcase>
    <testcase classname="migrated_playwright.test_scenarios" name="test_add_to_cart[msedge]" time="2.500">
        <error message="TimeoutError">Timeout</error>
    </testcase>
</testsuite>
"""


def test_parse_junit_xml_passing():
    parsed = parse_junit_xml(SAMPLE_PASSING_XML)
    assert parsed["suite_time"] == pytest.approx(4.5)
    assert len(parsed["testcases"]) == 2

    tc1 = parsed["testcases"][0]
    assert tc1["name"] == "test_login_valid"
    assert tc1["time"] == pytest.approx(2.1)
    assert tc1["failed"] is False
    assert tc1["failure_message"] == ""

    tc2 = parsed["testcases"][1]
    assert tc2["name"] == "test_search_with_results"
    assert tc2["time"] == pytest.approx(1.4)
    assert tc2["failed"] is False


def test_parse_junit_xml_failures_and_name_cleaning():
    parsed = parse_junit_xml(SAMPLE_MIXED_XML)
    assert parsed["suite_time"] == pytest.approx(6.2)
    assert len(parsed["testcases"]) == 3

    # Clean name should strip parameter suffix [msedge]
    tc1 = parsed["testcases"][0]
    assert tc1["name"] == "test_login_valid"
    assert tc1["failed"] is False

    tc2 = parsed["testcases"][1]
    assert tc2["name"] == "test_search_with_results"
    assert tc2["failed"] is True
    assert "AssertionError" in tc2["failure_message"]

    tc3 = parsed["testcases"][2]
    assert tc3["name"] == "test_add_to_cart"
    assert tc3["failed"] is True
    assert "TimeoutError" in tc3["failure_message"]


def test_percentile_95():
    assert percentile_95([]) == 0.0
    assert percentile_95([10.0]) == 10.0

    # For 100 evenly spaced numbers 1 to 100, p95 is ~95.05
    data_100 = [float(i) for i in range(1, 101)]
    p95 = percentile_95(data_100)
    assert 94.0 <= p95 <= 96.0

    # Small list [1.0, 2.0, 3.0, 4.0, 5.0]
    small = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile_95(small) == pytest.approx(4.8)


def test_aggregate_suite_metrics():
    run1 = {
        "suite_time": 10.0,
        "testcases": [
            {"name": "test_login", "time": 2.0, "failed": False},
            {"name": "test_search", "time": 1.0, "failed": False},
        ],
    }
    run2 = {
        "suite_time": 12.0,
        "testcases": [
            {"name": "test_login", "time": 2.5, "failed": False},
            {"name": "test_search", "time": 1.5, "failed": True},
        ],
    }
    run3 = {
        "suite_time": 8.0,
        "testcases": [
            {"name": "test_login", "time": 1.8, "failed": False},
            {"name": "test_search", "time": 1.2, "failed": False},
        ],
    }

    loc_info = {"files": 3, "total_lines": 120, "code_lines": 95}
    metrics = aggregate_suite_metrics([run1, run2, run3], loc_info)

    assert metrics["runs"] == 3
    assert metrics["loc"] == loc_info
    # Median of [10.0, 12.0, 8.0] is 10.0
    assert metrics["median_duration_s"] == pytest.approx(10.0)

    # Scenarios:
    # test_login: 0 failures / 3 runs -> failure_rate = 0.0
    login_sc = metrics["scenarios"]["test_login"]
    assert login_sc["total_executions"] == 3
    assert login_sc["failures"] == 0
    assert login_sc["failure_rate"] == 0.0
    # Median of [2.0, 2.5, 1.8] is 2.0
    assert login_sc["median_duration_s"] == pytest.approx(2.0)

    # test_search: 1 failure / 3 runs -> failure_rate = 1/3 ~ 0.3333
    search_sc = metrics["scenarios"]["test_search"]
    assert search_sc["total_executions"] == 3
    assert search_sc["failures"] == 1
    assert search_sc["failure_rate"] == pytest.approx(0.3333, rel=1e-3)


def test_count_loc(tmp_path: Path):
    code_dir = tmp_path / "sample_pkg"
    code_dir.mkdir()
    py1 = code_dir / "mod1.py"
    py1.write_text(
        "# Comment header\n\ndef foo():\n    return 42\n\n# Another comment\n",
        encoding="utf-8",
    )
    py2 = code_dir / "mod2.py"
    py2.write_text("x = 1\ny = 2\n", encoding="utf-8")

    result = count_loc(code_dir)
    assert result["files"] == 2
    # mod1 has 7 lines, 2 code lines ('def foo():', '    return 42')
    # mod2 has 2 lines, 2 code lines
    assert result["code_lines"] == 4
    assert result["total_lines"] == 8


def test_generate_benchmark_markdown():
    data = {
        "metadata": {
            "timestamp": "2026-11-10T20:00:00Z",
            "runs": 5,
            "python_version": "3.12.0",
        },
        "suites": {
            "legacy_selenium": {
                "runs": 5,
                "loc": {"files": 6, "total_lines": 350, "code_lines": 280},
                "median_duration_s": 25.5,
                "p95_duration_s": 28.0,
                "scenarios": {
                    "test_login_valid": {
                        "total_executions": 5,
                        "failures": 0,
                        "failure_rate": 0.0,
                        "median_duration_s": 3.2,
                        "p95_duration_s": 3.5,
                    }
                },
            },
            "migrated_playwright": {
                "runs": 5,
                "loc": {"files": 6, "total_lines": 260, "code_lines": 210},
                "median_duration_s": 12.0,
                "p95_duration_s": 13.5,
                "scenarios": {
                    "test_login_valid": {
                        "total_executions": 5,
                        "failures": 0,
                        "failure_rate": 0.0,
                        "median_duration_s": 1.5,
                        "p95_duration_s": 1.7,
                    }
                },
            },
        },
    }

    md = generate_benchmark_markdown(data)
    assert "# Benchmark Report" in md
    assert "25.500 s" in md
    assert "12.000 s" in md
    assert "test_login_valid" in md
    assert "faster" in md
