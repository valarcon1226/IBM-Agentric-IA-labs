from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import check_db_health, init_db


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "12-ci-cd-pipeline-api"


def test_health_endpoint_healthy(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["service"] == "12-ci-cd-pipeline-api"
    assert data["version"] == "1.0.0"


def test_health_endpoint_degraded(client: TestClient) -> None:
    with patch("app.main.check_db_health", return_value=False):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


def test_create_deployment_success(client: TestClient) -> None:
    payload = {
        "service_name": "order-service",
        "environment": "production",
        "version": "v1.2.0",
        "status": "successful",
        "deployed_by": "claudia",
        "description": "Initial production release",
    }
    response = client.post("/api/v1/deployments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["service_name"] == "order-service"
    assert data["environment"] == "production"
    assert data["version"] == "v1.2.0"
    assert data["status"] == "successful"
    assert data["deployed_by"] == "claudia"
    assert data["description"] == "Initial production release"
    assert "created_at" in data
    assert "updated_at" in data


def test_create_deployment_validation_error(client: TestClient) -> None:
    # Missing required fields
    response = client.post("/api/v1/deployments", json={"service_name": ""})
    assert response.status_code == 422


def test_list_deployments_empty(client: TestClient) -> None:
    response = client.get("/api/v1/deployments")
    assert response.status_code == 200
    assert response.json() == []


def test_list_deployments_and_filters(client: TestClient) -> None:
    dep1 = {
        "service_name": "api-gateway",
        "environment": "production",
        "version": "v1.0.0",
        "status": "successful",
    }
    dep2 = {
        "service_name": "worker",
        "environment": "staging",
        "version": "v1.0.1",
        "status": "failed",
    }
    dep3 = {
        "service_name": "frontend",
        "environment": "production",
        "version": "v2.0.0",
        "status": "successful",
    }
    client.post("/api/v1/deployments", json=dep1)
    client.post("/api/v1/deployments", json=dep2)
    client.post("/api/v1/deployments", json=dep3)

    # All items
    res_all = client.get("/api/v1/deployments")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 3

    # Filter by environment
    res_prod = client.get("/api/v1/deployments?environment=production")
    assert res_prod.status_code == 200
    assert len(res_prod.json()) == 2

    # Filter by status
    res_failed = client.get("/api/v1/deployments?status=failed")
    assert res_failed.status_code == 200
    assert len(res_failed.json()) == 1
    assert res_failed.json()[0]["service_name"] == "worker"

    # Pagination
    res_page = client.get("/api/v1/deployments?skip=1&limit=1")
    assert res_page.status_code == 200
    assert len(res_page.json()) == 1


def test_get_deployment_by_id_success(client: TestClient) -> None:
    payload = {
        "service_name": "billing-service",
        "environment": "production",
        "version": "v3.1.4",
    }
    create_res = client.post("/api/v1/deployments", json=payload)
    dep_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/deployments/{dep_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == dep_id
    assert data["service_name"] == "billing-service"


def test_get_deployment_by_id_not_found(client: TestClient) -> None:
    res = client.get("/api/v1/deployments/99999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_update_deployment_success(client: TestClient) -> None:
    payload = {
        "service_name": "auth-service",
        "environment": "staging",
        "version": "v0.9.0",
        "status": "pending",
    }
    create_res = client.post("/api/v1/deployments", json=payload)
    dep_id = create_res.json()["id"]

    update_payload = {
        "status": "successful",
        "description": "Promoted to staging verified",
    }
    put_res = client.put(f"/api/v1/deployments/{dep_id}", json=update_payload)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["status"] == "successful"
    assert data["description"] == "Promoted to staging verified"
    assert data["service_name"] == "auth-service"


def test_update_deployment_not_found(client: TestClient) -> None:
    res = client.put(
        "/api/v1/deployments/99999",
        json={"status": "failed"},
    )
    assert res.status_code == 404


def test_delete_deployment_success(client: TestClient) -> None:
    payload = {
        "service_name": "temp-service",
        "environment": "dev",
        "version": "v0.0.1",
    }
    create_res = client.post("/api/v1/deployments", json=payload)
    dep_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/deployments/{dep_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/v1/deployments/{dep_id}")
    assert get_res.status_code == 404


def test_delete_deployment_not_found(client: TestClient) -> None:
    res = client.delete("/api/v1/deployments/99999")
    assert res.status_code == 404


def test_settings_and_db_helpers() -> None:
    settings = get_settings()
    assert settings.APP_NAME == "12-ci-cd-pipeline-api"
    # Call init_db
    init_db()
    # Call check_db_health
    assert isinstance(check_db_health(), bool)
