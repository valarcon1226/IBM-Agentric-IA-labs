from fastapi.testclient import TestClient

from demo_app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "demo-app"
    assert "version" in data


def test_items_endpoint():
    response = client.get("/api/items")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["count"] == len(data["items"])
    assert data["count"] > 0


def test_process_rows_endpoint():
    payload = {"rows": 50, "pipeline": "test_pipeline"}
    response = client.post("/api/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline"] == "test_pipeline"
    assert data["processed_rows"] == 50
    assert data["status"] == "completed"


def test_process_rows_validation():
    # Negative rows should fail validation
    payload = {"rows": -5, "pipeline": "invalid"}
    response = client.post("/api/process", json=payload)
    assert response.status_code == 422


def test_error_endpoint():
    response = client.get("/api/error")
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Synthetic internal server error" in data["detail"]


def test_slow_endpoint():
    response = client.get("/api/slow?delay=0.01")
    assert response.status_code == 200
    data = response.json()
    assert data["delay_seconds"] == 0.01
    assert "Slow request finished" in data["message"]
