from fastapi.testclient import TestClient

from app import main


def test_health_ok(monkeypatch):
    async def ok() -> None:
        return None

    monkeypatch.setattr(main, "check_dependencies", ok)
    response = TestClient(main.app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_dependency_failure(monkeypatch):
    async def fail() -> None:
        raise ConnectionError("offline")

    monkeypatch.setattr(main, "check_dependencies", fail)
    response = TestClient(main.app).get("/health")
    assert response.status_code == 503
