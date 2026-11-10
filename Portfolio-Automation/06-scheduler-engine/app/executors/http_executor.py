import ipaddress
import socket
import time
import urllib.parse
from typing import Any

import httpx

from app.core.config import settings
from app.executors.base import ExecutionResult


def is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        )
    except ValueError:
        return True


def validate_url(url: str, allow_private: bool = False) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        msg = f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."
        raise ValueError(msg)

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname.")

    if not allow_private:
        try:
            # Resolve all IPs for hostname
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                if is_private_ip(ip_str):
                    raise ValueError(
                        f"SSRF Protection: Access to private/local IP '{ip_str}' is forbidden."
                    )
        except socket.gaierror as e:
            raise ValueError(f"DNS resolution failed for '{hostname}': {e}") from e


def execute_http(payload: dict[str, Any], allow_private: bool | None = None) -> ExecutionResult:
    start = time.perf_counter()
    url = payload.get("url")
    if not url:
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr="Missing required 'url' parameter in HTTP payload.",
            exit_code=-1,
            duration_ms=0,
        )

    effective_allow_private = (
        allow_private if allow_private is not None else settings.ALLOW_PRIVATE_TARGETS
    )

    try:
        validate_url(url, allow_private=effective_allow_private)
    except ValueError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=str(e),
            exit_code=-1,
            duration_ms=duration_ms,
        )

    method = payload.get("method", "GET").upper()
    headers = payload.get("headers")
    json_data = payload.get("json")
    data = payload.get("data")
    timeout = float(payload.get("timeout") or settings.EXECUTION_TIMEOUT_SECONDS)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                data=data,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            text_output = response.text[: settings.MAX_OUTPUT_BYTES]

            if 200 <= response.status_code < 400:
                return ExecutionResult(
                    status="SUCCESS",
                    stdout=text_output,
                    stderr="",
                    exit_code=response.status_code,
                    duration_ms=duration_ms,
                )
            else:
                return ExecutionResult(
                    status="FAILED",
                    stdout=text_output,
                    stderr=f"HTTP {response.status_code}: {response.reason_phrase}",
                    exit_code=response.status_code,
                    duration_ms=duration_ms,
                )
    except httpx.TimeoutException:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=f"Request timed out after {timeout} seconds.",
            exit_code=-1,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=f"HTTP request error: {str(exc)}",
            exit_code=-1,
            duration_ms=duration_ms,
        )
