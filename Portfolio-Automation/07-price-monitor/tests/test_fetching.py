"""Unit tests for PoliteFetcher: robots.txt, rate limits, and retry backoff."""

import time
from unittest.mock import MagicMock

import httpx
import pytest

from app.scraper.fetching import (
    PoliteFetcher,
    RetryableHTTPError,
    RobotsDisallowed,
    _domain,
    normalize_url,
)


def test_domain_extraction():
    assert _domain("https://api.mercadolibre.com/items/MLA123") == "api.mercadolibre.com"
    assert _domain("http://127.0.0.1:8087/products/keyboard.html") == "127.0.0.1:8087"


def test_normalize_url(monkeypatch):
    monkeypatch.setenv("IN_DOCKER", "true")
    assert (
        normalize_url("http://localhost:8087/products/item.html")
        == "http://demo-store:80/products/item.html"
    )
    assert (
        normalize_url("http://127.0.0.1:8087/products/item.html")
        == "http://demo-store:80/products/item.html"
    )

    monkeypatch.setenv("IN_DOCKER", "false")
    assert (
        normalize_url("http://localhost:8087/products/item.html")
        == "http://localhost:8087/products/item.html"
    )


def test_polite_fetcher_respects_robots_txt_allow():
    mock_client = MagicMock(spec=httpx.Client)
    # robots.txt response allows everything
    mock_robots_resp = httpx.Response(
        200,
        text="User-agent: *\nAllow: /\n",
        request=httpx.Request("GET", "http://example.com/robots.txt"),
    )
    # Page response
    mock_page_resp = httpx.Response(
        200,
        text="<html><body>Success</body></html>",
        request=httpx.Request("GET", "http://example.com/item.html"),
    )

    mock_client.get.side_effect = [mock_robots_resp, mock_page_resp]

    fetcher = PoliteFetcher(client=mock_client, min_interval=0.01)
    response = fetcher.get("http://example.com/item.html")
    assert response.status_code == 200
    assert "Success" in response.text


def test_polite_fetcher_raises_robots_disallowed():
    mock_client = MagicMock(spec=httpx.Client)
    # robots.txt forbids /private/
    mock_robots_resp = httpx.Response(
        200,
        text="User-agent: *\nDisallow: /private/\n",
        request=httpx.Request("GET", "http://example.com/robots.txt"),
    )
    mock_client.get.return_value = mock_robots_resp

    fetcher = PoliteFetcher(client=mock_client, min_interval=0.01)
    with pytest.raises(RobotsDisallowed):
        fetcher.get("http://example.com/private/secret.html")


def test_polite_fetcher_enforces_rate_limit():
    mock_client = MagicMock(spec=httpx.Client)
    mock_robots = httpx.Response(
        200,
        text="User-agent: *\nAllow: /\n",
        request=httpx.Request("GET", "http://example.com/robots.txt"),
    )
    mock_page = httpx.Response(
        200, text="OK", request=httpx.Request("GET", "http://example.com/page")
    )
    mock_client.get.side_effect = [mock_robots, mock_page, mock_page]

    min_interval = 0.05
    fetcher = PoliteFetcher(client=mock_client, min_interval=min_interval)

    start = time.monotonic()
    fetcher.get("http://example.com/page1")
    fetcher.get("http://example.com/page2")
    elapsed = time.monotonic() - start

    assert elapsed >= min_interval


def test_polite_fetcher_retries_on_500():
    mock_client = MagicMock(spec=httpx.Client)
    mock_robots = httpx.Response(
        200,
        text="User-agent: *\nAllow: /\n",
        request=httpx.Request("GET", "http://example.com/robots.txt"),
    )
    mock_fail = httpx.Response(500, request=httpx.Request("GET", "http://example.com/page"))
    mock_success = httpx.Response(
        200, text="Recovered", request=httpx.Request("GET", "http://example.com/page")
    )

    mock_client.get.side_effect = [mock_robots, mock_fail, mock_success]

    fetcher = PoliteFetcher(
        client=mock_client, min_interval=0.01, backoff_base=0.01, max_attempts=2
    )
    resp = fetcher.get("http://example.com/page")
    assert resp.status_code == 200
    assert resp.text == "Recovered"


def test_polite_fetcher_exhausts_retries_on_persistent_500():
    mock_client = MagicMock(spec=httpx.Client)
    mock_robots = httpx.Response(
        200,
        text="User-agent: *\nAllow: /\n",
        request=httpx.Request("GET", "http://example.com/robots.txt"),
    )
    mock_fail = httpx.Response(503, request=httpx.Request("GET", "http://example.com/page"))

    mock_client.get.side_effect = [mock_robots, mock_fail, mock_fail, mock_fail]

    fetcher = PoliteFetcher(
        client=mock_client, min_interval=0.01, backoff_base=0.01, max_attempts=2
    )
    with pytest.raises(RetryableHTTPError):
        fetcher.get("http://example.com/page")
