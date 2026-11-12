from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    task_type: Literal["HTTP", "SHELL", "PYTHON"]
    payload: dict[str, Any]
    schedule: str | None = Field(default=None, description="Cron expression e.g. '*/1 * * * *'")
    max_retries: int = Field(default=3, ge=0, le=20)
    retry_backoff: int = Field(default=60, ge=1, le=86400)
    depends_on: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    name: str | None = None
    task_type: Literal["HTTP", "SHELL", "PYTHON"] | None = None
    payload: dict[str, Any] | None = None
    schedule: str | None = None
    is_active: bool | None = None
    max_retries: int | None = Field(default=None, ge=0, le=20)
    retry_backoff: int | None = Field(default=None, ge=1, le=86400)
    depends_on: list[str] | None = None


class TaskResponse(BaseModel):
    task_id: str
    name: str
    task_type: str
    schedule: str | None = None
    is_active: bool
    last_run_at: datetime | None = None
    consecutive_failures: int = 0
    created_at: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)


class TaskDetailResponse(BaseModel):
    task_id: str
    name: str
    task_type: str
    payload: dict[str, Any]
    schedule: str | None = None
    max_retries: int
    retry_backoff: int
    is_active: bool
    last_run_at: datetime | None = None
    consecutive_failures: int = 0
    created_at: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)


class TaskRunResponse(BaseModel):
    run_id: str
    task_id: str
    status: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None


class TaskActionResponse(BaseModel):
    task_id: str
    name: str | None = None
    status: str


class TriggerResponse(BaseModel):
    task_id: str
    run_id: str | None = None
    message: str
