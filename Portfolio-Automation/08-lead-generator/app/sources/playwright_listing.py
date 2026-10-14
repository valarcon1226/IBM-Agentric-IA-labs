"""Playwright fetching (DECISIONES-08 L1): polite JS rendering."""

import logging

from playwright.sync_api import sync_playwright

from app.fetching import PoliteFetcher, RobotsDisallowed, _domain

logger = logging.getLogger(__name__)


def fetch_js_rendered(url: str, fetcher: PoliteFetcher) -> str:
    """Fetch a page using Playwright, respecting the fetcher's rate limit and robots.txt."""
    if not fetcher._robots_for(url).can_fetch(fetcher.user_agent, url):
        raise RobotsDisallowed(url)

    fetcher._wait_for_rate_limit(_domain(url))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=fetcher.user_agent)
        page = context.new_page()
        # Set a reasonable timeout
        page.goto(url, timeout=10000, wait_until="networkidle")
        html = page.content()
        browser.close()
        return html
