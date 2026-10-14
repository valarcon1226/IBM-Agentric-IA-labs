"""Polite HTTP fetching module.

Complies with ethical web scraping guidelines:
- Adheres to robots.txt
- Identifiable User-Agent
- Per-domain rate limiting (default: 1.0 req/s)
- Tenacity backoff on 429/5xx status codes
- No stealth, no proxies, no bot evasion
"""

import ipaddress
import logging
import os
import socket
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


class RetryableHTTPError(Exception):
    """Raised for 429 or 5xx status codes so tenacity can retry."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(f"{response.status_code} from {response.request.url}")


class RobotsDisallowed(Exception):
    """Raised when robots.txt forbids fetching the requested URL."""


class BlockedTarget(Exception):
    """Raised when a URL is not http(s) or points to an internal address (SSRF guard)."""


def check_target(url: str) -> None:
    """Reject non-http(s) URLs and, unless ALLOW_PRIVATE_TARGETS, internal addresses."""
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


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def normalize_url(url: str) -> str:
    """Rewrite localhost:8087 to demo-store when running inside container."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()

    # If running in Docker environment and host is localhost:8087 or 127.0.0.1:8087
    is_docker = (
        os.path.exists("/.dockerenv") or os.environ.get("IN_DOCKER", "false").lower() == "true"
    )
    if is_docker and netloc in ("localhost:8087", "127.0.0.1:8087"):
        # Rewrite to demo-store:80
        return url.replace(parsed.netloc, "demo-store:80", 1)

    return url


class PoliteFetcher:
    """Polite HTTP client with robots.txt check, domain rate limiting, and exponential retry."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        user_agent: str | None = None,
        min_interval: float | None = None,
        max_attempts: int = 3,
        backoff_base: float = 0.5,
    ) -> None:
        self.user_agent = user_agent or settings.SCRAPER_USER_AGENT
        self.min_interval = (
            min_interval if min_interval is not None else settings.SCRAPER_MIN_INTERVAL_SECONDS
        )
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._client = client
        self._owns_client = client is None
        self._last_request_at: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers={"User-Agent": self.user_agent},
                timeout=10.0,
                follow_redirects=True,
                event_hooks={"request": [_check_request]},
            )
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PoliteFetcher":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if domain not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            scheme = parsed.scheme or "http"
            robots_url = urljoin(f"{scheme}://{domain}/", "/robots.txt")
            try:
                response = self.client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser.parse([])
            except httpx.HTTPError:
                # If robots.txt cannot be reached, default to allow
                parser.parse([])
            self._robots[domain] = parser

        return self._robots[domain]

    def _wait_for_rate_limit(self, domain: str) -> None:
        last = self._last_request_at.get(domain)
        if last is not None:
            while (remaining := self.min_interval - (time.monotonic() - last)) > 0:
                time.sleep(remaining)
        self._last_request_at[domain] = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        """Perform a polite GET request."""
        clean_url = normalize_url(url)
        domain = _domain(clean_url)

        if not self._robots_for(clean_url).can_fetch(self.user_agent, clean_url):
            logger.warning("robots.txt disallowed fetch for %s", clean_url)
            raise RobotsDisallowed(f"robots.txt disallowed {clean_url}")

        self._wait_for_rate_limit(domain)

        @retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=self.backoff_base, max=5),
            retry=retry_if_exception_type(RetryableHTTPError),
            reraise=True,
        )
        def _do_request() -> httpx.Response:
            response = self.client.get(clean_url, headers={"User-Agent": self.user_agent})
            if response.status_code == 429 or response.status_code >= 500:
                raise RetryableHTTPError(response)
            return response

        return _do_request()
