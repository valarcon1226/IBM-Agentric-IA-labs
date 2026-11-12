"""SSRF guard: product URLs come from API users, so internal addresses are refused."""

import pytest

from app.core.config import settings
from app.scraper.fetching import BlockedTarget, PoliteFetcher, check_target


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/admin",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ],
)
def test_internal_or_non_http_targets_are_blocked(url, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", False)
    with pytest.raises(BlockedTarget):
        check_target(url)


def test_public_ip_is_allowed(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", False)
    check_target("http://93.184.215.14/")


def test_private_allowed_only_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", True)
    check_target("http://127.0.0.1:8087/products/keyboard.html")
    with pytest.raises(BlockedTarget):
        check_target("file:///etc/passwd")


def test_fetcher_blocks_before_any_request(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", False)
    with PoliteFetcher(min_interval=0) as fetcher, pytest.raises(BlockedTarget):
        fetcher.get("http://127.0.0.1:9/robots-should-not-be-fetched")


def test_api_rejects_non_http_url():
    from app.api.schemas import ProductBase

    with pytest.raises(ValueError):
        ProductBase(name="x", url="javascript:alert(1)", site_domain="demo")
