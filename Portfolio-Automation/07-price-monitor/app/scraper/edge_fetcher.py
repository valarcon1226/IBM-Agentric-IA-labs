"""Playwright fetcher using Microsoft Edge (channel='msedge').

Strictly used when client-side JavaScript rendering is required.
"""

import logging
import os

from playwright.sync_api import sync_playwright

from app.core.config import settings

logger = logging.getLogger(__name__)


def fetch_with_edge(
    url: str,
    user_agent: str | None = None,
    timeout_ms: int = 15000,
) -> str:
    """Fetch JavaScript-rendered HTML using Playwright with Microsoft Edge."""
    from app.scraper.fetching import check_target

    check_target(url)
    ua = user_agent or settings.SCRAPER_USER_AGENT
    channel = os.environ.get("PLAYWRIGHT_CHANNEL", "msedge")
    logger.info("Fetching %s with Microsoft Edge (channel=%s) via Playwright", url, channel)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel, headless=True)
        try:
            context = browser.new_context(user_agent=ua)
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()
