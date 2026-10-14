import httpx
import pytest

from app.fetching import PoliteFetcher, RetryableHTTPError, RobotsDisallowed


def _fetcher(handler, **kwargs) -> PoliteFetcher:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PoliteFetcher(client, min_interval=0, backoff_base=0.001, **kwargs)


def test_fetches_an_allowed_url():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="ok")

    fetcher = _fetcher(handler)
    response = fetcher.get("https://example.test/page.html")
    assert response.status_code == 200
    assert response.text == "ok"


def test_sends_an_identifiable_user_agent():
    seen_user_agents = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers.get("User-Agent"))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="ok")

    fetcher = _fetcher(handler, user_agent="LeadGeneratorBot/1.0 (+https://example.com/leadbot)")
    fetcher.get("https://example.test/page.html")
    assert all("LeadGeneratorBot" in ua for ua in seen_user_agents)


def test_respects_robots_disallow():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        return httpx.Response(200, text="ok")

    fetcher = _fetcher(handler)
    with pytest.raises(RobotsDisallowed):
        fetcher.get("https://example.test/private/page.html")


def test_missing_robots_txt_allows_fetching():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="ok")

    fetcher = _fetcher(handler)
    response = fetcher.get("https://example.test/page.html")
    assert response.status_code == 200


def test_retries_on_429_then_succeeds():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, text="ok")

    fetcher = _fetcher(handler)
    response = fetcher.get("https://example.test/page.html")
    assert response.status_code == 200
    assert attempts["count"] == 3


def test_retries_on_5xx_then_gives_up_after_max_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(503)

    fetcher = _fetcher(handler, max_attempts=3)
    with pytest.raises(RetryableHTTPError):
        fetcher.get("https://example.test/page.html")


def test_rate_limits_requests_to_the_same_domain():
    import time

    timestamps = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        timestamps.append(time.monotonic())
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = PoliteFetcher(client, min_interval=0.2)
    fetcher.get("https://example.test/a.html")
    fetcher.get("https://example.test/b.html")

    assert timestamps[1] - timestamps[0] >= 0.2
