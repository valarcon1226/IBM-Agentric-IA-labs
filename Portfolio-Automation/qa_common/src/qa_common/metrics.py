"""Latency metrics collection and statistics computation."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


class MetricsRecorder:
    """Records latency samples and computes p50, p95, p99 percentiles."""

    def __init__(self) -> None:
        self._samples: dict[str, list[float]] = {}

    def record(self, name: str, latency_s: float) -> None:
        """Record a single latency sample in seconds."""
        if name not in self._samples:
            self._samples[name] = []
        self._samples[name].append(latency_s)

    def compute(self) -> dict[str, dict[str, Any]]:
        """Compute count, p50, p95, and p99 for all recorded metrics."""
        results: dict[str, dict[str, Any]] = {}
        for name, samples in self._samples.items():
            if not samples:
                continue
            count = len(samples)
            if count == 1:
                val = samples[0]
                results[name] = {
                    "count": 1,
                    "p50": val,
                    "p95": val,
                    "p99": val,
                }
            else:
                # statistics.quantiles(data, n=100) computes 99 cut points:
                # index 49 corresponds to the 50th percentile (p50)
                # index 94 corresponds to the 95th percentile (p95)
                # index 98 corresponds to the 99th percentile (p99)
                quantiles = statistics.quantiles(samples, n=100, method="inclusive")
                results[name] = {
                    "count": count,
                    "p50": quantiles[49],
                    "p95": quantiles[94],
                    "p99": quantiles[98],
                }
        return results

    def save(self, output_path: str | Path = "results/metrics.json") -> None:
        """Save computed metrics to a JSON file, merging with existing keys."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if path.exists():
            # A corrupt file fails loudly instead of silently dropping earlier runs.
            with path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        data = self.compute()
        existing.update(data)
        with path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
