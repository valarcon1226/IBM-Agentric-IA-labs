"""Toxiproxy HTTP API client and toxic context manager."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import httpx


class ToxiproxyClient:
    """Client for Toxiproxy HTTP API (default http://127.0.0.1:8474)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8474") -> None:
        self.base_url = base_url.rstrip("/")

    def create_proxy(
        self,
        name: str,
        listen: str,
        upstream: str,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create a new proxy."""
        payload = {
            "name": name,
            "listen": listen,
            "upstream": upstream,
            "enabled": enabled,
        }
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            resp = client.post("/proxies", json=payload)
            if resp.status_code == 409:
                # Proxy already exists, return current config
                get_resp = client.get(f"/proxies/{name}")
                get_resp.raise_for_status()
                return get_resp.json()
            resp.raise_for_status()
            return resp.json()

    def get_proxy(self, name: str) -> dict[str, Any]:
        """Retrieve proxy configuration and active toxics."""
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            resp = client.get(f"/proxies/{name}")
            resp.raise_for_status()
            return resp.json()

    def delete_proxy(self, name: str) -> None:
        """Delete an existing proxy."""
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            resp = client.delete(f"/proxies/{name}")
            if resp.status_code != 404:
                resp.raise_for_status()

    def set_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable an existing proxy."""
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            resp = client.post(f"/proxies/{name}", json={"enabled": enabled})
            resp.raise_for_status()
            return resp.json()

    def add_toxic(
        self,
        proxy_name: str,
        toxic_name: str,
        toxic_type: str,
        stream: str = "downstream",
        toxicity: float = 1.0,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a toxic to a proxy."""
        payload: dict[str, Any] = {
            "name": toxic_name,
            "type": toxic_type,
            "stream": stream,
            "toxicity": toxicity,
            "attributes": attributes or {},
        }
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            resp = client.post(f"/proxies/{proxy_name}/toxics", json=payload)
            resp.raise_for_status()
            return resp.json()

    def remove_toxic(self, proxy_name: str, toxic_name: str) -> None:
        """Remove a toxic from a proxy."""
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            resp = client.delete(f"/proxies/{proxy_name}/toxics/{toxic_name}")
            if resp.status_code != 404:
                resp.raise_for_status()

    @contextmanager
    def toxic_context(
        self,
        proxy_name: str,
        toxic_name: str,
        toxic_type: str,
        stream: str = "downstream",
        toxicity: float = 1.0,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Context manager that adds a toxic and guarantees its removal on exit."""
        toxic = self.add_toxic(
            proxy_name=proxy_name,
            toxic_name=toxic_name,
            toxic_type=toxic_type,
            stream=stream,
            toxicity=toxicity,
            attributes=attributes,
        )
        try:
            yield toxic
        finally:
            self.remove_toxic(proxy_name, toxic_name)
