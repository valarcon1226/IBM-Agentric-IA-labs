"""Simple load generator script for demo-app.

Generates realistic traffic:
- GET /api/items (normal read load)
- POST /api/process (batch row processing for business metrics)
- Optional GET /api/error (simulated 500s)
- Optional GET /api/slow (simulated latency)
"""

import argparse
import sys
import time
from typing import Any

import httpx


def run_load(
    base_url: str = "http://127.0.0.1:8011",
    items_requests: int = 15,
    process_batches: int = 5,
    rows_per_batch: int = 120,
    with_errors: bool = False,
    with_slow: bool = False,
    timeout: float = 10.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Execute synthetic traffic against demo-app and return summary stats."""
    results = {
        "items_success": 0,
        "items_failed": 0,
        "process_success": 0,
        "process_failed": 0,
        "total_rows_processed": 0,
        "errors_triggered": 0,
        "slow_triggered": 0,
    }

    def _execute(c: httpx.Client):
        # 1. Normal read load
        for _ in range(items_requests):
            try:
                resp = c.get("/api/items")
                if resp.status_code == 200:
                    results["items_success"] += 1
                else:
                    results["items_failed"] += 1
            except Exception as e:
                print(f"[Warning] GET /api/items failed: {e}", file=sys.stderr)
                results["items_failed"] += 1

        # 2. Batch processing requests (business KPI)
        pipelines = ["sales_pipeline", "inventory_etl", "financial_enricher"]
        for i in range(process_batches):
            pipeline = pipelines[i % len(pipelines)]
            payload = {"rows": rows_per_batch, "pipeline": pipeline}
            try:
                resp = c.post("/api/process", json=payload)
                if resp.status_code == 200:
                    results["process_success"] += 1
                    results["total_rows_processed"] += rows_per_batch
                else:
                    results["process_failed"] += 1
            except Exception as e:
                print(f"[Warning] POST /api/process failed: {e}", file=sys.stderr)
                results["process_failed"] += 1

        # 3. Optional simulated errors
        if with_errors:
            for _ in range(3):
                try:
                    resp = c.get("/api/error")
                    if resp.status_code == 500:
                        results["errors_triggered"] += 1
                except Exception:
                    results["errors_triggered"] += 1

        # 4. Optional simulated slow requests
        if with_slow:
            try:
                resp = c.get("/api/slow", params={"delay": 0.05})
                if resp.status_code == 200:
                    results["slow_triggered"] += 1
            except Exception as e:
                print(f"[Warning] GET /api/slow failed: {e}", file=sys.stderr)

    if client is not None:
        _execute(client)
    else:
        with httpx.Client(base_url=base_url, timeout=timeout) as new_client:
            _execute(new_client)

    return results


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic load for demo-app")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8011",
        help="Base URL for demo-app (default: http://127.0.0.1:8011)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=20,
        help="Number of /api/items requests (default: 20)",
    )
    parser.add_argument(
        "--batches",
        type=int,
        default=5,
        help="Number of /api/process batches (default: 5)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=100,
        help="Rows per batch (default: 100)",
    )
    parser.add_argument(
        "--with-errors",
        action="store_true",
        help="Include synthetic 500 errors",
    )
    parser.add_argument(
        "--with-slow",
        action="store_true",
        help="Include synthetic slow requests",
    )

    args = parser.parse_args()

    print(f"Starting load generator against {args.base_url}...")
    start = time.perf_counter()
    summary = run_load(
        base_url=args.base_url,
        items_requests=args.requests,
        process_batches=args.batches,
        rows_per_batch=args.rows,
        with_errors=args.with_errors,
        with_slow=args.with_slow,
    )
    duration = time.perf_counter() - start

    print(f"Load generation finished in {duration:.2f}s:")
    print(f"  - Items requests: {summary['items_success']} ok, {summary['items_failed']} failed")
    print(
        f"  - Process batches: {summary['process_success']} ok, {summary['process_failed']} failed"
    )
    print(f"  - Total rows processed: {summary['total_rows_processed']}")
    print(f"  - Errors triggered: {summary['errors_triggered']}")
    print(f"  - Slow requests triggered: {summary['slow_triggered']}")


if __name__ == "__main__":
    main()
