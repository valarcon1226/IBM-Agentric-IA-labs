from fastapi.testclient import TestClient

from demo_app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_metrics_endpoint_status():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")


def test_metrics_contain_required_series():
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text

    # Standard SLA & operational metrics
    assert "http_requests_total" in text
    assert "http_request_duration_seconds" in text

    # Business metrics
    assert "business_processed_rows_total" in text
    assert "business_active_users" in text
    assert "business_operations_total" in text


def test_metrics_increment_on_operations():
    # Make a normal request
    client.get("/api/items")
    # Make a business process request
    client.post("/api/process", json={"rows": 77, "pipeline": "metrics_test_pipeline"})
    # Make a synthetic error request
    client.get("/api/error")

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    text = metrics_resp.text

    # Check endpoint breakdown in Prometheus format
    assert 'endpoint="/api/items"' in text
    assert 'status="200"' in text
    assert 'endpoint="/api/error"' in text
    assert 'status="500"' in text

    # Check business metrics updated
    assert 'pipeline="metrics_test_pipeline"' in text
    assert "business_active_users" in text
