import uuid
from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy_celery_beat.models import ModelBase

from app.core.config import settings

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    task_type = Column(String(50), nullable=False)  # HTTP, SHELL, PYTHON
    payload = Column(JSON, nullable=False)
    schedule = Column(String(100), nullable=True)  # Cron expression
    max_retries = Column(Integer, default=3)
    retry_backoff = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    runs = relationship("TaskRun", back_populates="task", cascade="all, delete-orphan")
    dependencies = relationship(
        "TaskDependency",
        foreign_keys="[TaskDependency.task_id]",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskRun(Base):
    __tablename__ = "task_runs"

    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False)  # SUCCESS, FAILED, RUNNING, SKIPPED, RETRYING
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    task = relationship("Task", back_populates="runs")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    task_id = Column(String(36), ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    depends_on_task_id = Column(
        String(36), ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True
    )

    task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")


def get_engine(db_url: str | None = None):
    url = db_url or settings.DATABASE_URL
    # Ensure postgresql:// uses psycopg2 driver if not specified
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return engine.execution_options(schema_translate_map={"celery_schema": None})


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    ModelBase.metadata.create_all(bind=eng)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
