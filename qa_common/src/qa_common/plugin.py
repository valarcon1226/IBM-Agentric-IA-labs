"""pytest plugin for qa_common: markers, metrics fixture, and traceability generator."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from qa_common.metrics import MetricsRecorder

_session_metrics = MetricsRecorder()
_traceability_records: list[dict[str, str]] = []


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "p1: PR gate test suite")
    config.addinivalue_line(
        "markers", "resilience: Resilience and fault injection test suite"
    )
    config.addinivalue_line("markers", "migration: Schema migration test suite")
    config.addinivalue_line("markers", "perf: Performance test suite")
    config.addinivalue_line("markers", "eval: Evaluation test suite")
    config.addinivalue_line(
        "markers", "req(id): Requirement identifier for traceability"
    )


@pytest.fixture
def metrics() -> Generator[MetricsRecorder, None, None]:
    """Fixture providing a metrics recorder."""
    yield _session_metrics


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: Any
) -> Generator[None, Any, None]:
    """Collect test outcomes for requirements traceability."""
    outcome = yield
    report = outcome.get_result()

    # The call phase decides the outcome; a failed or skipped setup never reaches it.
    if report.when == "call" or (report.when == "setup" and not report.passed):
        req_marker = item.get_closest_marker("req")
        if req_marker and req_marker.args:
            if hasattr(report, "wasxfail"):
                status = "XPASS" if report.passed else "XFAIL"
            elif report.when == "setup" and report.failed:
                status = "ERROR"
            else:
                status = report.outcome.upper()
            _traceability_records.append(
                {
                    "req_id": str(req_marker.args[0]),
                    "test_name": item.nodeid,
                    "outcome": status,
                }
            )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Save metrics and generate docs/TRACEABILITY.md."""
    # 1. Save metrics if any were recorded
    if _session_metrics._samples:
        results_dir = Path("results")
        results_dir.mkdir(parents=True, exist_ok=True)
        _session_metrics.save(results_dir / "metrics.json")

    # 2. Write traceability if any records were collected
    if _traceability_records:
        docs_dir = Path("docs")
        docs_dir.mkdir(parents=True, exist_ok=True)
        trace_file = docs_dir / "TRACEABILITY.md"

        # Merge with the previous matrix so separate runs (PR gate, nightly) add up,
        # the same way metrics.json is merged; this run wins for tests it ran.
        by_test: dict[str, dict[str, str]] = {}
        if trace_file.exists():
            for line in trace_file.read_text(encoding="utf-8").splitlines():
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) == 3 and cells[1].startswith("`"):
                    name = cells[1].strip("`")
                    by_test[name] = {"req_id": cells[0], "test_name": name, "outcome": cells[2]}
        for rec in _traceability_records:
            by_test[rec["test_name"]] = rec

        sorted_records = sorted(
            by_test.values(),
            key=lambda r: (r["req_id"], r["test_name"]),
        )

        content_lines = [
            "# Traceability Matrix",
            "",
            "Generated automatically by qa_common pytest plugin.",
            "",
            "| Requirement | Test | Outcome |",
            "|-------------|------|---------|",
        ]
        for rec in sorted_records:
            content_lines.append(
                f"| {rec['req_id']} | `{rec['test_name']}` | {rec['outcome']} |"
            )
        content_lines.append("")

        with trace_file.open("w", encoding="utf-8") as f:
            f.write("\n".join(content_lines))
