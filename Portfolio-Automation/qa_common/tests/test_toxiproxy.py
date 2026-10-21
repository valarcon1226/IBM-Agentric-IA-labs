"""Unit tests for ToxiproxyClient with mocked HTTP transport."""

from __future__ import annotations

import httpx
import pytest
from qa_common.toxiproxy import ToxiproxyClient


def test_toxiproxy_methods() -> None:
    calls: list[str] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/proxies" and request.method == "POST":
            return httpx.Response(
                201, json={"name": "test_p", "listen": "0.0.0.0:8000"}
            )
        if (
            request.url.path.startswith("/proxies/test_p/toxics")
            and request.method == "POST"
        ):
            return httpx.Response(
                200, json={"name": "latency_toxic", "type": "latency"}
            )
        if (
            request.url.path.startswith("/proxies/test_p/toxics")
            and request.method == "DELETE"
        ):
            return httpx.Response(204)
        if request.url.path == "/proxies/test_p" and request.method == "POST":
            return httpx.Response(200, json={"name": "test_p", "enabled": False})
        if request.url.path == "/proxies/test_p" and request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)

    client = ToxiproxyClient("http://127.0.0.1:8474")

    # Monkeypatch transport in httpx.Client
    real_client_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        real_client_init(self, *args, **kwargs)

    pytest.MonkeyPatch().setattr(httpx.Client, "__init__", patched_init)

    p = client.create_proxy("test_p", "0.0.0.0:8000", "upstream:8000")
    assert p["name"] == "test_p"

    res = client.set_enabled("test_p", False)
    assert res["enabled"] is False

    with client.toxic_context(
        "test_p", "latency_toxic", "latency", attributes={"latency": 100}
    ) as t:
        assert t["name"] == "latency_toxic"

    assert "POST /proxies" in calls
    assert "POST /proxies/test_p" in calls
    assert "POST /proxies/test_p/toxics" in calls
    assert "DELETE /proxies/test_p/toxics/latency_toxic" in calls
