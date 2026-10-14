"""Every /api/v1 route needs the Bearer token: this API can run scripts."""

from fastapi.testclient import TestClient

from app.main import app


def test_api_rejects_missing_or_wrong_token(client):
    bare = TestClient(app)
    assert bare.get("/api/v1/tasks").status_code == 401
    wrong = bare.get("/api/v1/tasks", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    assert client.get("/api/v1/tasks").status_code == 200
