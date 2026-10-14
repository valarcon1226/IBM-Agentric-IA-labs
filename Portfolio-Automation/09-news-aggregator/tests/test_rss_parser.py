"""Unit tests for RSS feed parsing."""

from pathlib import Path

import pytest

from ingestion.rss_parser import parse_rss_feed


def test_parse_valid_rss_fixture(fixtures_dir: Path):
    feed_path = fixtures_dir / "feed_tech_a.xml"
    articles = parse_rss_feed(feed_path.read_text(encoding="utf-8"))

    assert len(articles) == 2
    item1 = articles[0]
    assert "OpenAI presenta su nuevo modelo GPT-5" in item1["title"]
    assert item1["url"] == "https://technews-a.local/openai-gpt-5-announcement"
    assert item1["author"] == "Carlos Gomez"
    assert "razonamiento profundo" in item1["raw_content"]
    assert item1["published_date"] is not None

    item2 = articles[1]
    assert "Kubernetes 1.32" in item2["title"]
    assert item2["url"] == "https://technews-a.local/kubernetes-1-32-release"


def test_parse_feeds_b_and_c(fixtures_dir: Path):
    articles_b = parse_rss_feed((fixtures_dir / "feed_tech_b.xml").read_text(encoding="utf-8"))
    assert len(articles_b) == 2
    assert "Llega GPT-5" in articles_b[0]["title"]
    assert "ransomware" in articles_b[1]["title"].lower()

    articles_c = parse_rss_feed((fixtures_dir / "feed_tech_c.xml").read_text(encoding="utf-8"))
    assert len(articles_c) == 2
    assert "redefine los estándares" in articles_c[0]["title"]
    assert (
        "Wall Street" in articles_c[1]["raw_content"]
        or "acciones" in articles_c[1]["title"].lower()
    )


def test_parse_invalid_feed():
    with pytest.raises(ValueError):
        parse_rss_feed("<?xml version='1.0'?><invalid>not a feed</invalid>")


def test_local_paths_and_internal_urls_are_refused(fixtures_dir: Path, monkeypatch):
    from api.config import settings
    from ingestion.net import BlockedTarget

    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", False)
    for target in (
        str(fixtures_dir / "feed_tech_a.xml"),
        "file:///etc/passwd",
        "http://127.0.0.1:5432/",
        "http://169.254.169.254/latest/",
    ):
        with pytest.raises(BlockedTarget):
            parse_rss_feed(target)
