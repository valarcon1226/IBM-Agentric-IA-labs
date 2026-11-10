"""TEST DOUBLE: Scripted OpenAI-compatible upstream server for fault injection.

*** NOTE: THIS MODULE IS A TEST DOUBLE AND IS NOT PART OF THE SYSTEM UNDER TEST (SUT) ***

Implements:
- POST /v1/chat/completions (streaming and non-streaming)
- POST /control/script: configure next response behaviors (ok, 429, 500, 400, delay_ms, cut_stream)
- GET /control/attempts: retrieve full log of all received request attempts
- POST /control/reset: clear attempt log and behavior queue
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional


@dataclass
class AttemptLog:
    request_id: str
    timestamp: float
    path: str
    method: str
    model: str
    stream: bool
    headers: Dict[str, str]
    body: Dict[str, Any]
    response_status: int
    behavior_applied: Dict[str, Any]


@dataclass
class Behavior:
    status: int = 200
    delay_ms: int = 0
    retry_after: Optional[int] = None
    cut_after_chunks: Optional[int] = None  # for streaming cutoff without finish_reason
    error_message: Optional[str] = None
    response_text: str = "Hello from fake upstream"


class FakeUpstreamState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.behavior_queue: List[Behavior] = []
        self.default_behavior: Behavior = Behavior(status=200, response_text="Default response")
        self.attempts: List[AttemptLog] = []

    def set_script(self, behaviors: List[Dict[str, Any]]) -> None:
        with self.lock:
            self.behavior_queue = [Behavior(**b) for b in behaviors]

    def reset(self) -> None:
        with self.lock:
            self.behavior_queue.clear()
            self.attempts.clear()
            self.default_behavior = Behavior(status=200, response_text="Default response")

    def get_next_behavior(self) -> Behavior:
        with self.lock:
            if self.behavior_queue:
                return self.behavior_queue.pop(0)
            return self.default_behavior

    def record_attempt(self, log: AttemptLog) -> None:
        with self.lock:
            self.attempts.append(log)

    def get_attempts(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [asdict(a) for a in self.attempts]


GLOBAL_STATE = FakeUpstreamState()


class FakeUpstreamHandler(BaseHTTPRequestHandler):
    # Quiet logging during automated test runs
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        if self.path == "/control/script":
            self._handle_control_script()
        elif self.path == "/control/reset":
            self._handle_control_reset()
        elif self.path in ("/v1/chat/completions", "/chat/completions"):
            self._handle_chat_completions()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Endpoint not found"}')

    def do_GET(self) -> None:
        if self.path == "/control/attempts":
            self._handle_control_attempts()
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "double": "fake_upstream"}')
        else:
            self.send_response(404)
            self.end_headers()

    def _read_json_body(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"_raw": raw.decode("utf-8", errors="replace")}

    def _handle_control_script(self) -> None:
        body = self._read_json_body()
        behaviors = body.get("behaviors", [])
        GLOBAL_STATE.set_script(behaviors)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "queued": len(behaviors)}).encode())

    def _handle_control_reset(self) -> None:
        GLOBAL_STATE.reset()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "reset": true}')

    def _handle_control_attempts(self) -> None:
        attempts = GLOBAL_STATE.get_attempts()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(attempts).encode())

    def _handle_chat_completions(self) -> None:
        req_id = f"fake-{uuid.uuid4()}"
        start_time = time.time()
        body = self._read_json_body()
        model = body.get("model", "fake-model")
        stream = bool(body.get("stream", False))

        behavior = GLOBAL_STATE.get_next_behavior()

        if behavior.delay_ms > 0:
            time.sleep(behavior.delay_ms / 1000.0)

        # Record normalized lowercase headers for consistent assertions
        normalized_headers = {k.lower(): v for k, v in self.headers.items()}
        attempt = AttemptLog(
            request_id=req_id,
            timestamp=start_time,
            path=self.path,
            method="POST",
            model=model,
            stream=stream,
            headers=normalized_headers,
            body=body,
            response_status=behavior.status,
            behavior_applied=asdict(behavior),
        )

        GLOBAL_STATE.record_attempt(attempt)

        # Check for error status
        if behavior.status != 200:
            self.send_response(behavior.status)
            self.send_header("Content-Type", "application/json")
            if behavior.status == 429 and behavior.retry_after is not None:
                self.send_header("Retry-After", str(behavior.retry_after))
            self.end_headers()

            error_msg = behavior.error_message or f"HTTP {behavior.status} error from fake upstream"
            err_payload = {
                "error": {
                    "message": error_msg,
                    "type": "invalid_request_error" if behavior.status == 400 else "upstream_error",
                    "code": behavior.status,
                }
            }
            self.wfile.write(json.dumps(err_payload).encode())
            return

        # Success path (200)
        if stream:
            self._send_streaming_response(req_id, model, behavior)
        else:
            self._send_non_streaming_response(req_id, model, behavior)

    def _send_non_streaming_response(self, req_id: str, model: str, behavior: Behavior) -> None:
        text = behavior.response_text
        prompt_tokens = 15
        completion_tokens = max(1, len(text.split()))

        resp = {
            "id": req_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        raw_bytes = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

    def _send_streaming_response(self, req_id: str, model: str, behavior: Behavior) -> None:
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        words = behavior.response_text.split()
        if not words:
            words = ["Hello", "world"]

        cut_after = behavior.cut_after_chunks

        try:
            for idx, word in enumerate(words):
                if cut_after is not None and idx >= cut_after:
                    # Abruptly cut the stream without finish_reason and without [DONE]
                    try:
                        self.wfile.flush()
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                    except Exception:
                        pass
                    return

                chunk = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": word + " "},
                            "finish_reason": None,
                        }
                    ],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()

            # If not cut, send final chunk with finish_reason: stop
            if cut_after is None:
                final_chunk = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
                self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


class FakeUpstreamServer:
    """Manages lifecycle of FakeUpstream ThreadingHTTPServer."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8001) -> None:
        self.host = host
        self.port = port
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        GLOBAL_STATE.reset()
        self.server = ThreadingHTTPServer((self.host, self.port), FakeUpstreamHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            self.thread = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Fake Upstream Server (Test Double)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    print(f"Starting Fake Upstream Test Double on http://{args.host}:{args.port}")
    server = ThreadingHTTPServer((args.host, args.port), FakeUpstreamHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Fake Upstream...")
        server.shutdown()


if __name__ == "__main__":
    main()
