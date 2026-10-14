from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.core.celery_app import run_scheduled_task
from app.models.database import Task, TaskDependency, TaskRun


def test_dependency_unmet_no_runs(test_db: Session):
    task_a = Task(name="Task A", task_type="PYTHON", payload={"script": "demo_success.py"})
    task_b = Task(name="Task B", task_type="PYTHON", payload={"script": "demo_dependent.py"})
    test_db.add_all([task_a, task_b])
    test_db.flush()

    dep = TaskDependency(task_id=task_b.task_id, depends_on_task_id=task_a.task_id)
    test_db.add(dep)
    test_db.commit()

    task_b_id = str(task_b.task_id)
    res = run_scheduled_task(task_b_id)
    assert res["status"] == "SKIPPED"
    assert "expected SUCCESS" in res["reason"]

    # Verify run record in DB
    run = test_db.query(TaskRun).filter(TaskRun.task_id == task_b_id).first()
    assert run is not None
    assert run.status == "SKIPPED"


def test_dependency_unmet_failed_run(test_db: Session):
    task_a = Task(name="Task A", task_type="PYTHON", payload={"script": "demo_failure.py"})
    task_b = Task(name="Task B", task_type="PYTHON", payload={"script": "demo_dependent.py"})
    test_db.add_all([task_a, task_b])
    test_db.flush()

    dep = TaskDependency(task_id=task_b.task_id, depends_on_task_id=task_a.task_id)
    run_a = TaskRun(task_id=task_a.task_id, status="FAILED", exit_code=1)
    test_db.add_all([dep, run_a])
    test_db.commit()

    task_b_id = str(task_b.task_id)
    res = run_scheduled_task(task_b_id)
    assert res["status"] == "SKIPPED"

    run = test_db.query(TaskRun).filter(TaskRun.task_id == task_b_id).first()
    assert run is not None
    assert run.status == "SKIPPED"


def test_dependency_met_success_run(test_db: Session):
    task_a = Task(name="Task A", task_type="PYTHON", payload={"script": "demo_success.py"})
    task_b = Task(name="Task B", task_type="PYTHON", payload={"script": "demo_dependent.py"})
    test_db.add_all([task_a, task_b])
    test_db.flush()

    dep = TaskDependency(task_id=task_b.task_id, depends_on_task_id=task_a.task_id)
    run_a = TaskRun(task_id=task_a.task_id, status="SUCCESS", exit_code=0)
    test_db.add_all([dep, run_a])
    test_db.commit()

    task_b_id = str(task_b.task_id)
    res = run_scheduled_task(task_b_id)
    assert res["status"] == "SUCCESS"

    run = (
        test_db.query(TaskRun)
        .filter(TaskRun.task_id == task_b_id)
        .order_by(TaskRun.started_at.desc())
        .first()
    )
    assert run is not None
    assert run.status == "SUCCESS"
    assert "Dependent task running" in run.stdout


def test_alert_triggered_after_consecutive_failures(test_db: Session):
    task = Task(
        name="Failing Task",
        task_type="PYTHON",
        payload={"script": "demo_failure.py"},
        max_retries=0,  # No retries -> fail immediately
        consecutive_failures=2,  # Already failed twice; next failure makes it 3
    )
    test_db.add(task)
    test_db.commit()

    task_id = str(task.task_id)

    mock_client = MagicMock()
    mock_post = MagicMock()
    mock_client.__enter__.return_value.post = mock_post

    with patch("app.core.celery_app.httpx.Client", return_value=mock_client):
        res = run_scheduled_task(task_id)
        assert res["status"] == "FAILED"
        test_db.expire_all()
        updated_task = test_db.query(Task).filter(Task.task_id == task_id).first()
        assert updated_task is not None
        assert updated_task.consecutive_failures == 3

        # Assert webhook alert was sent
        assert mock_post.called
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["template_name"] == "slack_alert"
        assert payload["channels"] == ["slack"]
        assert payload["priority"] == "high"
        assert payload["event"] == "task_consecutive_failures"
        assert payload["consecutive_failures"] == 3


def test_dependency_ignores_run_still_in_progress(test_db: Session):
    task_a = Task(name="Task A", task_type="PYTHON", payload={"script": "demo_success.py"})
    task_b = Task(name="Task B", task_type="PYTHON", payload={"script": "demo_dependent.py"})
    test_db.add_all([task_a, task_b])
    test_db.flush()
    test_db.add(TaskDependency(task_id=task_b.task_id, depends_on_task_id=task_a.task_id))
    test_db.add(TaskRun(task_id=task_a.task_id, status="SUCCESS", exit_code=0))
    test_db.commit()
    # A starts again at the same tick as B; B must judge A by its last finished run.
    test_db.add(TaskRun(task_id=task_a.task_id, status="RUNNING"))
    test_db.commit()

    assert run_scheduled_task(str(task_b.task_id))["status"] == "SUCCESS"
