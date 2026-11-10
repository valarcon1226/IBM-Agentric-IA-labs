"""Unit tests for HTML text extraction and robots.txt checking."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ingestion.text_extractor import (
    extract_text_from_html,
    is_allowed_by_robots,
)


def test_extract_text_from_fixture(fixtures_dir: Path):
    html_path = fixtures_dir / "sample_article.html"
    html_content = html_path.read_text(encoding="utf-8")

    text = extract_text_from_html(html_content)
    assert "modelos de lenguaje grande" in text.lower()
    assert "asistentes inteligentes" in text.lower()
    # Confirm HTML tags were stripped
    assert "<p>" not in text
    assert "</article>" not in text


def test_extract_text_empty():
    assert extract_text_from_html("") == ""
    assert extract_text_from_html("   ") == ""


def test_robots_txt_allowed():
    # Non-http scheme is always allowed
    assert is_allowed_by_robots("file:///local/path") is True

    # Mocked 200 robots allowing user agent
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "User-agent: *\nDisallow: /admin\nAllow: /articles"

    with patch("httpx.Client.get", return_value=mock_resp):
        assert is_allowed_by_robots("https://example.com/articles/ai-news") is True
        assert is_allowed_by_robots("https://example.com/admin/login") is False


def test_robots_txt_not_found_defaults_to_allowed():
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.Client.get", return_value=mock_resp):
        assert is_allowed_by_robots("https://example.com/any-path") is True
