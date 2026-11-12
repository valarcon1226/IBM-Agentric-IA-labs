"""Tests for asynchronous web crawler."""

import pytest

from app.crawler import SiteCrawler


@pytest.mark.asyncio
async def test_crawler_mock_site(mock_server: str):
    """Crawler explores internal links, respects max_pages, and fetches auxiliary files."""
    crawler = SiteCrawler(allow_local=True)
    result = await crawler.crawl(f"{mock_server}/", max_pages=5)

    assert result["base_url"] == f"{mock_server}/"
    assert result["is_local"] is True

    pages = result["pages"]
    assert len(pages) >= 2  # At least index and about/menu

    # Auxiliary files checked
    assert result["robots_response"][0] == 200
    assert "Disallow: /admin/" in result["robots_response"][1]

    assert result["sitemap_response"][0] == 200
    assert "<urlset" in result["sitemap_response"][1]

    assert result["llms_response"][0] == 200
    assert "Mock Coffee Store" in result["llms_response"][1]

    # Verify broken link detected on index page
    index_page = next((p for p in pages if p["url"] == f"{mock_server}/" or p["url"].endswith("/index.html")), None)
    assert index_page is not None
    assert any("/broken-404" in bl for bl in index_page["broken_links"])


@pytest.mark.asyncio
async def test_crawler_respects_max_pages(mock_server: str):
    """Crawler stops strictly at max_pages."""
    crawler = SiteCrawler(allow_local=True)
    result = await crawler.crawl(f"{mock_server}/", max_pages=1)
    assert len(result["pages"]) == 1
