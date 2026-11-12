from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import PeriodicTask

from app.models.database import Task, TaskRun


def test_create_task_and_sync_beat(client: TestClient, test_db: Session):
    payload = {
        "name": "Nightly Database Backup",
        "task_type": "SHELL",
        "payload": {"command": "backup.sh", "args": ["db_prod"]},
        "schedule": "0 2 * * *",
        "max_retries": 3,
        "retry_backoff": 60,
    }
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "CREATED"
    task_id = data["task_id"]

    # Verify task in DB
    task = test_db.query(Task).filter(Task.task_id == task_id).first()
    assert task is not None
    assert task.name == "Nightly Database Backup"

    # Verify PeriodicTask created and synced
    pt = test_db.query(PeriodicTask).filter(PeriodicTask.name == f"task-{task_id}").first()
    assert pt is not None
    assert pt.enabled is True
    assert pt.schedule_model is not None
    assert pt.schedule_model.minute == "0"
    assert pt.schedule_model.hour == "2"


def test_list_and_get_task(client: TestClient, test_db: Session):
    payload = {
        "name": "Health Ping",
        "task_type": "HTTP",
        "payload": {"url": "https://httpbin.org/get"},
        "schedule": "*/5 * * * *",
    }
    create_res = client.post("/api/v1/tasks", json=payload)
    task_id = create_res.json()["task_id"]

    # List tasks
    list_res = client.get("/api/v1/tasks")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(t["task_id"] == task_id for t in items)

    # Get single task
    detail_res = client.get(f"/api/v1/tasks/{task_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["name"] == "Health Ping"
    assert detail["task_type"] == "HTTP"


def test_update_and_pause_task(client: TestClient, test_db: Session):
    payload = {
        "name": "Active Task",
        "task_type": "PYTHON",
        "payload": {"script": "demo_success.py"},
        "schedule": "*/1 * * * *",
    }
    create_res = client.post("/api/v1/tasks", json=payload)
    task_id = create_res.json()["task_id"]

    # Pause task
    update_res = client.put(f"/api/v1/tasks/{task_id}", json={"is_active": False})
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "UPDATED"

    # Verify PeriodicTask disabled
    pt = test_db.query(PeriodicTask).filter(PeriodicTask.name == f"task-{task_id}").first()
    assert pt.enabled is False

    # Resume task
    update_res2 = client.put(f"/api/v1/tasks/{task_id}", json={"is_active": True})
    assert update_res2.status_code == 200
    test_db.refresh(pt)
    assert pt.enabled is True


def test_delete_task(client: TestClient, test_db: Session):
    payload = {
        "name": "To Be Deleted",
        "task_type": "PYTHON",
        "payload": {"script": "demo_success.py"},
        "schedule": "*/10 * * * *",
    }
    create_res = client.post("/api/v1/tasks", json=payload)
    task_id = create_res.json()["task_id"]

    del_res = client.delete(f"/api/v1/tasks/{task_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "DELETED"

    task = test_db.query(Task).filter(Task.task_id == task_id).first()
    assert task is None

    pt = test_db.query(PeriodicTask).filter(PeriodicTask.name == f"task-{task_id}").first()
    assert pt is None


def test_trigger_task(client: TestClient):
    payload = {
        "name": "Manual Trigger Task",
        "task_type": "PYTHON",
        "payload": {"script": "demo_success.py"},
    }
    create_res = client.post("/api/v1/tasks", json=payload)
    task_id = create_res.json()["task_id"]

    with patch("app.api.routes.run_scheduled_task.delay") as mock_delay:
        mock_delay.return_value.id = "mocked-celery-id"
        trig_res = client.post(f"/api/v1/tasks/{task_id}/trigger")
        assert trig_res.status_code == 200
        assert trig_res.json()["message"] == "Task manually enqueued."
        mock_delay.assert_called_once_with(task_id, is_manual=True)


def test_get_runs(client: TestClient, test_db: Session):
    task = Task(
        name="Task with Runs",
        task_type="PYTHON",
        payload={"script": "demo_success.py"},
    )
    test_db.add(task)
    test_db.flush()

    run = TaskRun(
        task_id=task.task_id,
        status="SUCCESS",
        stdout="Job executed",
        exit_code=0,
        duration_ms=120,
    )
    test_db.add(run)
    test_db.commit()

    runs_res = client.get(f"/api/v1/tasks/{task.task_id}/runs")
    assert runs_res.status_code == 200
    runs = runs_res.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "SUCCESS"
    assert runs[0]["duration_ms"] == 120

    all_runs_res = client.get("/api/v1/runs")
    assert all_runs_res.status_code == 200
    assert len(all_runs_res.json()) >= 1


def test_invalid_cron(client: TestClient):
    payload = {
        "name": "Bad Cron",
        "task_type": "PYTHON",
        "payload": {"script": "demo_success.py"},
        "schedule": "bad cron",
    }
    res = client.post("/api/v1/tasks", json=payload)
    assert res.status_code == 400
    assert "cron" in res.json()["detail"].lower()
