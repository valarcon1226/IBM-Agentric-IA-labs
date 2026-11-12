"""Reproduce FINDING-001: the same order delivered several times at once returns HTTP 500.

Sends each order in N simultaneous deliveries (same body, different delivery id) and counts
the status codes. Standard library only. Needs the stack from docker-compose.perf.yml running.

    python scripts/repro_duplicate_race.py [--orders 10] [--deliveries 4]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "20-ecommerce-order-automation"
    / "samples"
    / "woocommerce_order_created.json"
)


def deliver(url: str, body: bytes, signature: str, delivery_id: str, statuses: list[int]) -> None:
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-wc-webhook-signature": signature,
            "x-wc-webhook-topic": "order.created",
            "x-wc-webhook-id": delivery_id,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            statuses.append(response.status)
    except urllib.error.HTTPError as err:
        statuses.append(err.code)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--secret", default="perf_test_woocommerce_secret_key")
    parser.add_argument("--orders", type=int, default=10)
    parser.add_argument("--deliveries", type=int, default=4)
    args = parser.parse_args()

    order = json.loads(SAMPLE.read_text(encoding="utf-8"))
    url = f"{args.base_url}/webhooks/woocommerce"
    statuses: list[int] = []
    first_id = int(time.time() * 1000) % 100_000_000

    for n in range(args.orders):
        order["id"] = first_id + n
        order["number"] = str(first_id + n)
        body = json.dumps(order).encode()
        digest = hmac.new(args.secret.encode(), body, hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode()
        threads = [
            threading.Thread(
                target=deliver, args=(url, body, signature, f"race-{first_id}-{n}-{i}", statuses)
            )
            for i in range(args.deliveries)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    counts = Counter(statuses)
    print(f"{args.orders} orders x {args.deliveries} simultaneous deliveries")
    for status, count in sorted(counts.items()):
        print(f"HTTP {status}: {count}")


if __name__ == "__main__":
    main()
