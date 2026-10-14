"""RSS feed ingestion module using feedparser."""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import feedparser

from ingestion.net import check_target, safe_client
from ingestion.text_extractor import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)


def parse_datetime(struct_time: time.struct_time | None) -> datetime:
    """Converts a feedparser struct_time into a UTC-aware datetime."""
    if struct_time:
        try:
            return datetime.fromtimestamp(time.mktime(struct_time), tz=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def extract_content(entry: Any) -> str:
    """Extracts the cleanest body text available in the feed entry."""
    if hasattr(entry, "content") and entry.content:
        for c in entry.content:
            if isinstance(c, dict) and "value" in c:
                return str(c["value"]).strip()
    if hasattr(entry, "summary") and entry.summary:
        return str(entry.summary).strip()
    if hasattr(entry, "description") and entry.description:
        return str(entry.description).strip()
    return ""


def parse_rss_feed(source_input: str) -> list[dict[str, Any]]:
    """Parses an RSS feed from an http(s) URL or an XML string (never a local file path).

    Returns a list of standardized article dicts:
    - title: str
    - url: str
    - author: str
    - published_date: datetime
    - raw_content: str
    """
    if source_input.lstrip().startswith("<"):
        feed = feedparser.parse(source_input)
    else:
        # feedparser would also open local files; fetch it ourselves through the SSRF guard.
        check_target(source_input)
        with safe_client(DEFAULT_USER_AGENT) as client:
            resp = client.get(source_input)
            resp.raise_for_status()
        feed = feedparser.parse(resp.content)

    if not feed.entries and (feed.bozo or not getattr(feed, "version", None)):
        reason = getattr(feed, "bozo_exception", None) or "no valid RSS/Atom structure found"
        logger.warning(f"Error parsing feed input: {reason}")
        raise ValueError(f"Failed to parse RSS feed: {reason}")

    articles: list[dict[str, Any]] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue

        author = getattr(entry, "author", "") or getattr(entry, "creator", "")
        pub_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        pub_date = parse_datetime(pub_parsed)
        content = extract_content(entry)

        articles.append({
            "title": title,
            "url": link,
            "author": author.strip() if author else "Redacción",
            "published_date": pub_date,
            "raw_content": content,
        })

    return articles
