from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_example_env_satisfies_settings(monkeypatch):
    for line in (Path(__file__).resolve().parents[1] / ".env.example").read_text().splitlines():
        key, value = line.split("=", 1)
        monkeypatch.setenv(key, value)
    assert Settings(_env_file=None).API_KEY == "change_me_api_key"


def test_health_reports_dependency_failure(monkeypatch):
    from app import db

    def fail():
        raise ConnectionError("offline")

    monkeypatch.setattr(db, "check_dependencies", fail)
    assert TestClient(app).get("/health").status_code == 503


def test_production_app_exposes_documented_routes():
    paths = {(route.path, next(iter(route.methods))) for route in app.routes if route.methods}
    assert {
        ("/api/v1/intake/upload", "POST"),
        ("/api/v1/intake/{upload_id}", "GET"),
        ("/api/v1/intake/{upload_id}/review", "GET"),
        ("/api/v1/intake/{upload_id}/review", "POST"),
    } <= paths
