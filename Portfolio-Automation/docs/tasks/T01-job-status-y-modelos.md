# T01 — Enum `JobStatus` y modelos ORM tipados (proyecto 04)

**Objetivo:** un único lugar para los estados de job, y modelos ORM al estilo tipado de
SQLAlchemy 2.0 (`Mapped[...]`), para que mypy acepte asignar valores en las tareas siguientes.
**No cambia comportamiento HTTP.**

**Archivos que puedes tocar (solo estos):**
- `04-data-cleaning-api/app/core/database.py`
- `04-data-cleaning-api/app/models/db.py`
- `04-data-cleaning-api/tests/test_models.py` (nuevo)

## Antes de empezar

Desde `04-data-cleaning-api`, corre las compuertas (ver `.github/copilot-instructions.md`).
Esperado: **27 passed**. Si no, detente.

## Paso 1 — `app/core/database.py`

Reemplaza el archivo completo por este contenido. EXACTO:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Dependency to get the database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## Paso 2 — `app/models/db.py`

Reemplaza el archivo completo. EXACTO:

```python
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobStatus(StrEnum):
    """Lifecycle of an async job. Values match the SQL default in init-db.sql."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def _now() -> datetime:
    return datetime.now(UTC)


class SchemaModel(Base):
    """SQLAlchemy ORM model for schemas."""

    __tablename__ = "schemas"

    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    jobs: Mapped[list["JobModel"]] = relationship(back_populates="schema")


class JobModel(Base):
    """SQLAlchemy ORM model for jobs."""

    __tablename__ = "jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schema_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schemas.schema_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=JobStatus.PENDING.value
    )
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_file_path: Mapped[str | None] = mapped_column(String(512))
    output_file_path: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schema: Mapped[SchemaModel | None] = relationship(back_populates="jobs")
```

## Paso 3 — `tests/test_models.py` (nuevo)

EXACTO:

```python
from app.models.db import JobModel, JobStatus


def test_job_status_values_match_sql():
    assert [s.value for s in JobStatus] == ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


def test_job_schema_fk_sets_null_on_delete():
    (fk,) = JobModel.__table__.c.schema_id.foreign_keys
    assert fk.ondelete == "SET NULL"
```

## Verificación

1. Compuertas → **29 passed**, ruff y mypy limpios.
2. `Select-String -Path app -Recurse -Pattern "declarative_base|Column\("` → **sin coincidencias**.

## Terminado cuando

Las dos verificaciones pasan. Reporta y marca `T01` como `DONE` en `docs/tasks/README.md`.
