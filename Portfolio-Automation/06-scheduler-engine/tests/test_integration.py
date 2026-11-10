import os

import httpx
import pytest

pytestmark = pytest.mark.integration

API_BASE = os.environ.get("INTEGRATION_API_URL", "http://127.0.0.1:8006")
AUTH = {"Authorization": f"Bearer {os.environ.get('API_KEY', 'change_me_api_key')}"}


@pytest.fixture(scope="module")
def api_available():
    try:
        with httpx.Client(headers=AUTH, timeout=3.0) as client:
            resp = client.get(f"{API_BASE}/health")
            if resp.status_code == 200:
                return True
    except Exception:
        pass
    pytest.skip(f"Integration API at {API_BASE} is not reachable. Skipping integration test.")


def test_integration_health(api_available):
    with httpx.Client(headers=AUTH, timeout=5.0) as client:
        resp = client.get(f"{API_BASE}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


def test_integration_crud_and_trigger(api_available):
    with httpx.Client(headers=AUTH, timeout=10.0) as client:
        # 1. Create task
        task_data = {
            "name": "Integration Test Task",
            "task_type": "PYTHON",
            "payload": {"script": "demo_success.py", "args": ["integration"]},
            "schedule": "*/1 * * * *",
        }
        res = client.post(f"{API_BASE}/api/v1/tasks", json=task_data)
        assert res.status_code == 201
        task_id = res.json()["task_id"]

        # 2. Get task
        get_res = client.get(f"{API_BASE}/api/v1/tasks/{task_id}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Integration Test Task"

        # 3. Trigger manual execution
        trig_res = client.post(f"{API_BASE}/api/v1/tasks/{task_id}/trigger")
        assert trig_res.status_code == 200
        assert "manually enqueued" in trig_res.json()["message"]

        # 4. Delete task
        del_res = client.delete(f"{API_BASE}/api/v1/tasks/{task_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "DELETED"
