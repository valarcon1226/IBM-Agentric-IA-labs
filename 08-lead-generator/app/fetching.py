"""Polite HTTP fetching (DECISIONES-08 L1): robots.txt, identifiable User-Agent, a per-domain
rate limit (1 req/s by default) and `tenacity` backoff on 429/5xx. No proxies, no stealth.
"""

import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class RetryableHTTPError(Exception):
    """Raised for a 429/5xx response so tenacity can back off and retry."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(f"{response.status_code} from {response.request.url}")


class RobotsDisallowed(Exception):
    """robots.txt forbids fetching this URL for our User-Agent."""


def _domain(url: str) -> str:
    return urlparse(url).netloc


class PoliteFetcher:
    def __init__(
        self,
        client: httpx.Client,
        user_agent: str = "LeadGeneratorBot/1.0 (+https://example.com/leadbot)",
        min_interval: float = 1.0,
        max_attempts: int = 4,
        backoff_base: float = 0.5,
    ) -> None:
        self.client = client
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._last_request_at: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        domain = _domain(url)
        if domain not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = urljoin(f"https://{domain}/", "/robots.txt")
            try:
                response = self.client.get(
                    robots_url, headers={"User-Agent": self.user_agent}, timeout=5.0
                )
                parser.parse(response.text.splitlines())
            except httpx.HTTPError:
                # No robots.txt reachable -> treat as "allow all" (can't be stricter than the
                # site itself chose not to publish rules).
                parser.parse([])
            self._robots[domain] = parser
        return self._robots[domain]

    def _wait_for_rate_limit(self, domain: str) -> None:
        last = self._last_request_at.get(domain)
        if last is not None:
            # Loop rather than a single sleep: OS wake-ups can fire a few ms early (especially
            # on Windows' ~15ms timer granularity), letting two requests slip under min_interval.
            while (remaining := self.min_interval - (time.monotonic() - last)) > 0:
                time.sleep(remaining)
        self._last_request_at[domain] = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        if not self._robots_for(url).can_fetch(self.user_agent, url):
            raise RobotsDisallowed(url)

        self._wait_for_rate_limit(_domain(url))

        @retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=self.backoff_base, max=10),
            retry=retry_if_exception_type(RetryableHTTPError),
            reraise=True,
        )
        def _do_request() -> httpx.Response:
            response = self.client.get(url, headers={"User-Agent": self.user_agent})
            if response.status_code == 429 or response.status_code >= 500:
                raise RetryableHTTPError(response)
            return response

        return _do_request()
