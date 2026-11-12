"""Tests for FastAPI audit endpoints."""

from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


def test_api_health():
    """Health check returns 200 and ok status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "seo-aeo-audit"}


def test_api_rejects_private_ip_without_allow_local():
    """POST /audit rejects private addresses with HTTP 400."""
    payload = {
        "url": "http://127.0.0.1:8899",
        "max_pages": 2,
        "allow_local": False,
    }
    resp = client.post("/audit", json=payload)
    assert resp.status_code == 400
    assert "local" in resp.json()["detail"] or "privada" in resp.json()["detail"]


def test_api_audit_mock_server_json(mock_server: str):
    """POST /audit executes audit against mock server and returns JSON summary."""
    payload = {
        "url": f"{mock_server}/",
        "max_pages": 3,
        "allow_local": True,
        "run_lighthouse": False,
        "lang": "es",
    }
    resp = client.post("/audit", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "overall_score" in data
    assert "seo_score" in data
    assert "aeo_score" in data
    assert "issues" in data
    assert data["pages_analyzed"] >= 1


def test_api_audit_mock_server_html(mock_server: str):
    """POST /audit/html returns rendered HTML report."""
    payload = {
        "url": f"{mock_server}/",
        "max_pages": 2,
        "allow_local": True,
        "run_lighthouse": False,
        "lang": "es",
    }
    resp = client.post("/audit/html", json=payload)
    assert resp.status_code == 200
    assert "SEO &amp; AEO" in resp.text
    assert "Mock Coffee" in resp.text
