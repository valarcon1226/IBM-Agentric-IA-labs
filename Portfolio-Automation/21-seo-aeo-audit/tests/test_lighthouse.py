"""Tests for Lighthouse integration and graceful fallback."""

from unittest.mock import patch

from app.lighthouse import find_browser_executable, run_lighthouse_audit


def test_find_browser_executable():
    """Finds Chrome or Edge on Windows."""
    browser = find_browser_executable()
    # On this machine, Edge or Chrome is installed
    assert browser is not None
    assert "edge" in browser.lower() or "chrome" in browser.lower()


def test_lighthouse_fallback_when_no_browser():
    """When no browser executable exists, gracefully returns skipped status."""
    with patch("app.lighthouse.find_browser_executable", return_value=None):
        res = run_lighthouse_audit("https://ejemplo.com")
        assert res["available"] is False
        assert res["skipped"] is True
        assert "Chrome no detectado" in res["reason"]
        assert res["performance"] is None


def test_lighthouse_fallback_when_npx_missing():
    """When npx is missing, gracefully returns skipped status."""
    with patch("shutil.which", return_value=None):
        res = run_lighthouse_audit("https://ejemplo.com")
        assert res["available"] is False
        assert res["skipped"] is True
        assert res["performance"] is None
