"""Text extraction module using httpx, trafilatura, and robots.txt compliance."""

import logging
import re
import urllib.robotparser
from urllib.parse import urlparse

import httpx
import trafilatura

from ingestion.net import check_target, safe_client

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "NewsIntelligenceBot/1.0 (+http://news-aggregator.local/bot)"


def is_allowed_by_robots(
    url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 3.0
) -> bool:
    """Checks whether crawling this URL is permitted according to robots.txt."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()

    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            resp = client.get(robots_url)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                return rp.can_fetch(user_agent, url)
            if resp.status_code in (401, 403):
                return False
            # 404 or other status codes typically imply no crawling restrictions
            return True
    except Exception as exc:
        logger.debug(f"Could not fetch robots.txt for {robots_url}: {exc}")
        return True


def extract_text_from_html(html: str) -> str:
    """Extracts main body content from HTML using trafilatura with regex fallback."""
    if not html or not html.strip():
        return ""

    try:
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            output_format="txt",
        )
        if extracted and extracted.strip():
            return extracted.strip()
    except Exception as exc:
        logger.debug(f"trafilatura extraction error: {exc}")

    # Fallback: strip tags and clean whitespace
    clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def fetch_and_extract_url(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 10.0,
    check_robots: bool = True,
) -> str:
    """Fetches article HTML and extracts body text while respecting robots.txt."""
    if check_robots and not is_allowed_by_robots(url, user_agent=user_agent):
        raise PermissionError(f"Crawling blocked by robots.txt for URL: {url}")

    check_target(url)
    with safe_client(user_agent, timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return extract_text_from_html(resp.text)
