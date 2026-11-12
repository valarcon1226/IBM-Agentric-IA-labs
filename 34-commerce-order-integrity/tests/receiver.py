"""Mock Webhook Receiver using standard library http.server running in a thread."""

from __future__ import annotations

import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class WebhookRecord:
    """Stores delivery metadata for a received webhook."""

    def __init__(
        self,
        event_type: str,
        event_id: str,
        received_at: float,
        payload: dict[str, Any],
        status_code: int,
    ) -> None:
        self.event_type = event_type
        self.event_id = event_id
        self.received_at = received_at
        self.payload = payload
        self.status_code = status_code


class MockWebhookReceiver:
    """Configurable webhook receiver with delay and failure rate injection."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8085) -> None:
        self.host = host
        self.port = port
        self.delay_s = 0.0
        self.failure_rate = 0.0
        self.records: list[WebhookRecord] = []
        self.delivery_times: dict[str, list[float]] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start receiver HTTP server in a background thread."""
        receiver_self = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                # Suppress noisy HTTP request logging
                pass

            def do_POST(self) -> None:
                # Simulate consumer delay if configured
                if receiver_self.delay_s > 0:
                    time.sleep(receiver_self.delay_s)

                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    payload = {}

                event_type = self.headers.get("Saleor-Event", "UNKNOWN")
                # Identify event id or order id from payload/headers
                event_id = (
                    self.headers.get("Saleor-Event-Id")
                    or (payload[0].get("id") if isinstance(payload, list) and payload else None)
                    or (payload.get("id") if isinstance(payload, dict) else None)
                    or f"event-{time.time_ns()}"
                )

                now = time.time()

                # Determine if request fails with 500
                should_fail = random.random() < receiver_self.failure_rate
                status = 500 if should_fail else 200

                with receiver_self._lock:
                    rec = WebhookRecord(
                        event_type=event_type,
                        event_id=str(event_id),
                        received_at=now,
                        payload=payload if isinstance(payload, dict) else {},
                        status_code=status,
                    )
                    receiver_self.records.append(rec)
                    if str(event_id) not in receiver_self.delivery_times:
                        receiver_self.delivery_times[str(event_id)] = []
                    receiver_self.delivery_times[str(event_id)].append(now)

                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                resp = json.dumps({"status": "error" if should_fail else "ok"}).encode()
                self.wfile.write(resp)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shutdown the receiver server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5.0)

    def clear(self) -> None:
        """Clear recorded deliveries."""
        with self._lock:
            self.records.clear()
            self.delivery_times.clear()
