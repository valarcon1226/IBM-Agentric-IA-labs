"""Outbound HTTP for user-supplied URLs: http(s) only, no internal addresses (SSRF guard)."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from api.config import settings


class BlockedTarget(ValueError):
    """Raised when a URL is not http(s) or points to an internal address."""


def check_target(url: str) -> None:
    """Reject non-http(s) URLs and, unless ALLOW_PRIVATE_TARGETS, non-public addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise BlockedTarget(f"Only http(s) URLs with a host are allowed: {url}")
    if settings.ALLOW_PRIVATE_TARGETS:
        return
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedTarget(f"Cannot resolve {parsed.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise BlockedTarget(f"{parsed.hostname} resolves to a non-public address ({ip})")


def _check_request(request: httpx.Request) -> None:
    # Runs for every request, redirects included.
    check_target(str(request.url))


def safe_client(user_agent: str, timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": user_agent},
        event_hooks={"request": [_check_request]},
    )
