"""Resilience test: Backpressure from slow warehouse sink recovers without data loss."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from qa_common import ToxiproxyClient, assert_target

from tests.conftest import (
    DEFAULT_SOURCE_URL,
    get_rpk_consumer_lag,
    wait_for_consumer_lag_zero,
)
from tools.reconcile import reconcile_ledger
from tools.workload import WorkloadGenerator

logger = logging.getLogger("test_slow_sink")


@pytest.mark.resilience
@pytest.mark.req("REQ-CDC-003")
def test_slow_sink_backpressure_and_recovery() -> None:
    """Inject 200ms latency on warehouse for 2 min at 500 rows/s, measure catch-up time."""
    target_rate = 500.0
    slowdown_duration = 120.0  # 2 minutes of slowdown
    toxic_latency_ms = 200

    toxi = ToxiproxyClient(base_url="http://127.0.0.1:8474")
    # Clean any stale toxics
    try:
        toxi.remove_toxic("warehouse_pg", "sink_latency")
    except Exception:
        pass

    # Start workload generator in background thread
    start_id = int(time.time() * 100)
    generator = WorkloadGenerator(
        db_url=DEFAULT_SOURCE_URL,
        seed=101,
        target_rate=target_rate,
        initial_id=start_id,
    )

    workload_thread = threading.Thread(
        target=lambda: generator.run(duration_seconds=360.0),
        daemon=True,
    )
    workload_thread.start()

    logger.info("Establishing pre-fault baseline for 10 seconds...")
    time.sleep(10.0)
    baseline_lag = get_rpk_consumer_lag()
    logger.info("Pre-fault baseline consumer lag: %d", baseline_lag)

    lag_samples: list[dict[str, Any]] = [
        {"t_offset": 0.0, "lag": baseline_lag, "phase": "baseline"}
    ]

    # Inject 200ms latency to warehouse via Toxiproxy
    logger.info("Injecting %d ms latency toxic on warehouse_pg...", toxic_latency_ms)
    toxi.add_toxic(
        proxy_name="warehouse_pg",
        toxic_name="sink_latency",
        toxic_type="latency",
        attributes={"latency": toxic_latency_ms},
    )

    t_fault_start = time.monotonic()
    peak_lag = baseline_lag

    try:
        # Sample consumer-group lag every 5 s during the 2 min slowdown
        while (time.monotonic() - t_fault_start) < slowdown_duration:
            time.sleep(5.0)
            elapsed = time.monotonic() - t_fault_start
            current_lag = get_rpk_consumer_lag()
            peak_lag = max(peak_lag, current_lag)
            lag_samples.append(
                {"t_offset": round(elapsed, 2), "lag": current_lag, "phase": "slowdown"}
            )
            logger.info(
                "[Slowdown t=%.1fs] Consumer lag: %d (Peak: %d)",
                elapsed,
                current_lag,
                peak_lag,
            )

    finally:
        # Remove the toxic
        logger.info("Removing sink_latency toxic from warehouse_pg...")
        toxi.remove_toxic("warehouse_pg", "sink_latency")
        t_remove = time.monotonic()

    logger.info("Toxic removed. Workload continues running; measuring catch-up time...")
    catch_up_threshold = max(baseline_lag + 10, 20)

    recovered = False
    catch_up_time = 0.0
    recovery_timeout = 240.0  # Allow up to 4 minutes to observe catch-up

    while (time.monotonic() - t_remove) < recovery_timeout:
        time.sleep(2.0)
        t_now = time.monotonic()
        lag_now = get_rpk_consumer_lag()
        elapsed_since_fault = t_now - t_fault_start
        lag_samples.append(
            {
                "t_offset": round(elapsed_since_fault, 2),
                "lag": lag_now,
                "phase": "recovering",
            }
        )
        logger.info(
            "[Recovery t=%.1fs] Consumer lag: %d (Target <= %d)",
            t_now - t_remove,
            lag_now,
            catch_up_threshold,
        )

        if lag_now <= catch_up_threshold:
            catch_up_time = t_now - t_remove
            recovered = True
            logger.info("Pipeline caught up to baseline in %.2f s!", catch_up_time)
            break

    # Stop the workload
    generator.stop()
    workload_thread.join(timeout=10.0)

    # Save lag samples in results/
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    samples_path = results_dir / "slow_sink_lag_samples.json"
    with samples_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "target_rate_rps": target_rate,
                "toxic_latency_ms": toxic_latency_ms,
                "slowdown_duration_s": slowdown_duration,
                "baseline_lag": baseline_lag,
                "peak_lag": peak_lag,
                "catch_up_time_s": catch_up_time,
                "samples": lag_samples,
            },
            f,
            indent=2,
        )
    logger.info("Saved %d lag samples to %s", len(lag_samples), samples_path)

    assert recovered, (
        f"Pipeline failed to catch up within {recovery_timeout}s after toxic removal "
        f"(last lag={lag_now})"
    )

    # Assert against targets.toml (catch_up_time <= 180s)
    assert_target("catch_up_time_slowdown_seconds", catch_up_time)

    # Wait until all remaining lag drains to 0
    wait_for_consumer_lag_zero(timeout=60.0)

    # Reconcile tables
    logger.info("Reconciling tables post-backpressure test...")
    rec_result = reconcile_ledger(chunk_size=10_000)
    assert rec_result.total_differences == 0, (
        f"Reconciler found {rec_result.total_differences} differences "
        f"(missing={len(rec_result.missing_keys)}, extra={len(rec_result.extra_keys)}, "
        f"changed={len(rec_result.changed_keys)})"
    )
    assert_target("rows_differ_after_fault", rec_result.total_differences)
