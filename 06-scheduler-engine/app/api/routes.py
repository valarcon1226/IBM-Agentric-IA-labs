import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import CrontabSchedule, PeriodicTask, PeriodicTaskChanged

from app.api.schemas import (
    TaskActionResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    TaskRunResponse,
    TaskUpdate,
    TriggerResponse,
)
from app.core.celery_app import run_scheduled_task
from app.core.security import verify_api_key
from app.models.database import Task, TaskDependency, TaskRun, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["tasks"], dependencies=[Depends(verify_api_key)])


def sync_periodic_task(db: Session, task: Task) -> None:
    pt_name = f"task-{task.task_id}"
    pt = db.query(PeriodicTask).filter(PeriodicTask.name == pt_name).first()

    if task.schedule and task.schedule.strip():
        parts = task.schedule.strip().split()
        if len(parts) != 5:
            raise HTTPException(
                status_code=400,
                detail="Schedule must be a standard 5-part cron expression (e.g. '*/1 * * * *')",
            )
        spec = {
            "minute": parts[0],
            "hour": parts[1],
            "day_of_month": parts[2],
            "month_of_year": parts[3],
            "day_of_week": parts[4],
            "timezone": "UTC",
        }
        crontab = db.query(CrontabSchedule).filter_by(**spec).first()
        if not crontab:
            crontab = CrontabSchedule(**spec)
            db.add(crontab)
            db.flush()

        if not pt:
            pt = PeriodicTask(
                name=pt_name,
                task="app.core.celery_app.run_scheduled_task",
                args=json.dumps([str(task.task_id)]),
                enabled=bool(task.is_active),
            )
            pt.schedule_model = crontab
            db.add(pt)
        else:
            pt.enabled = bool(task.is_active)
            pt.args = json.dumps([str(task.task_id)])
            pt.schedule_model = crontab
    else:
        if pt:
            pt.enabled = False

    try:
        PeriodicTaskChanged.update_from_session(db, commit=False)
    except Exception as exc:
        logger.warning(f"Could not update PeriodicTaskChanged: {exc}")


@router.post("/tasks", response_model=TaskActionResponse, status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db)) -> Any:
    task = Task(
        name=data.name,
        task_type=data.task_type,
        payload=data.payload,
        schedule=data.schedule,
        max_retries=data.max_retries,
        retry_backoff=data.retry_backoff,
        is_active=True,
    )
    db.add(task)
    db.flush()

    if data.depends_on:
        for dep_id in data.depends_on:
            dep_task = db.query(Task).filter(Task.task_id == dep_id).first()
            if not dep_task:
                msg = f"Dependency task '{dep_id}' not found."
                raise HTTPException(status_code=400, detail=msg)
            dep = TaskDependency(task_id=task.task_id, depends_on_task_id=dep_id)
            db.add(dep)

    sync_periodic_task(db, task)
    db.commit()
    db.refresh(task)

    return TaskActionResponse(
        task_id=str(task.task_id),
        name=task.name,
        status="CREATED",
    )


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)) -> Any:
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    result = []
    for t in tasks:
        deps = [d.depends_on_task_id for d in t.dependencies]
        result.append(
            TaskResponse(
                task_id=str(t.task_id),
                name=t.name,
                task_type=t.task_type,
                schedule=t.schedule,
                is_active=bool(t.is_active),
                last_run_at=t.last_run_at,
                consecutive_failures=t.consecutive_failures or 0,
                created_at=t.created_at,
                depends_on=deps,
            )
        )
    return result


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
def get_task(task_id: str, db: Session = Depends(get_db)) -> Any:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    deps = [d.depends_on_task_id for d in task.dependencies]
    return TaskDetailResponse(
        task_id=str(task.task_id),
        name=task.name,
        task_type=task.task_type,
        payload=task.payload,
        schedule=task.schedule,
        max_retries=task.max_retries or 3,
        retry_backoff=task.retry_backoff or 60,
        is_active=bool(task.is_active),
        last_run_at=task.last_run_at,
        consecutive_failures=task.consecutive_failures or 0,
        created_at=task.created_at,
        depends_on=deps,
    )


@router.put("/tasks/{task_id}", response_model=TaskActionResponse)
def update_task(task_id: str, data: TaskUpdate, db: Session = Depends(get_db)) -> Any:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if data.name is not None:
        task.name = data.name
    if data.task_type is not None:
        task.task_type = data.task_type
    if data.payload is not None:
        task.payload = data.payload
    if data.schedule is not None:
        task.schedule = data.schedule
    if data.is_active is not None:
        task.is_active = data.is_active
    if data.max_retries is not None:
        task.max_retries = data.max_retries
    if data.retry_backoff is not None:
        task.retry_backoff = data.retry_backoff

    if data.depends_on is not None:
        db.query(TaskDependency).filter(TaskDependency.task_id == task_id).delete()
        for dep_id in data.depends_on:
            dep_task = db.query(Task).filter(Task.task_id == dep_id).first()
            if not dep_task:
                msg = f"Dependency task '{dep_id}' not found."
                raise HTTPException(status_code=400, detail=msg)
            db.add(TaskDependency(task_id=task_id, depends_on_task_id=dep_id))

    sync_periodic_task(db, task)
    db.commit()

    return TaskActionResponse(
        task_id=str(task.task_id),
        name=task.name,
        status="UPDATED",
    )


@router.delete("/tasks/{task_id}", response_model=TaskActionResponse)
def delete_task(task_id: str, db: Session = Depends(get_db)) -> Any:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    pt_name = f"task-{task.task_id}"
    pt = db.query(PeriodicTask).filter(PeriodicTask.name == pt_name).first()
    if pt:
        db.delete(pt)
        try:
            PeriodicTaskChanged.update_from_session(db, commit=False)
        except Exception:
            pass

    db.delete(task)
    db.commit()

    return TaskActionResponse(
        task_id=task_id,
        status="DELETED",
    )


@router.post("/tasks/{task_id}/trigger", response_model=TriggerResponse)
def trigger_task(task_id: str, db: Session = Depends(get_db)) -> Any:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async_res = run_scheduled_task.delay(str(task.task_id), is_manual=True)

    return TriggerResponse(
        task_id=str(task.task_id),
        run_id=async_res.id if hasattr(async_res, "id") else None,
        message="Task manually enqueued.",
    )


@router.get("/tasks/{task_id}/runs", response_model=list[TaskRunResponse])
def get_task_runs(
    task_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Any:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    runs = (
        db.query(TaskRun)
        .filter(TaskRun.task_id == task_id)
        .order_by(TaskRun.started_at.desc())
        .limit(limit)
        .all()
    )

    return [
        TaskRunResponse(
            run_id=str(r.run_id),
            task_id=str(r.task_id),
            status=r.status,
            stdout=r.stdout,
            stderr=r.stderr,
            exit_code=r.exit_code,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_ms=r.duration_ms,
        )
        for r in runs
    ]


@router.get("/runs", response_model=list[TaskRunResponse])
def list_all_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    runs = db.query(TaskRun).order_by(TaskRun.started_at.desc()).limit(limit).all()
    return [
        TaskRunResponse(
            run_id=str(r.run_id),
            task_id=str(r.task_id),
            status=r.status,
            stdout=r.stdout,
            stderr=r.stderr,
            exit_code=r.exit_code,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_ms=r.duration_ms,
        )
        for r in runs
    ]
