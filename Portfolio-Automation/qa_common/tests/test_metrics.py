"""Unit tests for percentile math in MetricsRecorder."""

from __future__ import annotations

import json
from pathlib import Path

from qa_common.metrics import MetricsRecorder


def test_metrics_single_sample() -> None:
    recorder = MetricsRecorder()
    recorder.record("test_op", 0.15)
    data = recorder.compute()

    assert "test_op" in data
    assert data["test_op"]["count"] == 1
    assert data["test_op"]["p50"] == 0.15
    assert data["test_op"]["p95"] == 0.15
    assert data["test_op"]["p99"] == 0.15


def test_metrics_percentile_math() -> None:
    recorder = MetricsRecorder()
    # 100 values from 1 to 100
    for i in range(1, 101):
        recorder.record("latency", float(i))

    data = recorder.compute()
    assert data["latency"]["count"] == 100
    # In 1..100 with inclusive quantiles (n=100):
    # p50 is 50.5 (or around 50)
    assert 49.0 <= data["latency"]["p50"] <= 52.0
    # p95 is ~95
    assert 94.0 <= data["latency"]["p95"] <= 96.0
    # p99 is ~99
    assert 98.0 <= data["latency"]["p99"] <= 100.0


def test_metrics_save(tmp_path: Path) -> None:
    recorder = MetricsRecorder()
    recorder.record("op", 1.23)
    out_file = tmp_path / "results" / "metrics.json"
    recorder.save(out_file)

    assert out_file.is_file()
    with out_file.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["op"]["count"] == 1
    assert loaded["op"]["p50"] == 1.23
