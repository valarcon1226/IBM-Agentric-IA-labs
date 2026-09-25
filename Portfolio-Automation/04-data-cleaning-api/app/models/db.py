import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SchemaModel(Base):
    """SQLAlchemy ORM model for schemas."""

    __tablename__ = "schemas"

    schema_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    definition = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    jobs = relationship("JobModel", back_populates="schema")


class JobModel(Base):
    """SQLAlchemy ORM model for jobs."""

    __tablename__ = "jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_id = Column(
        UUID(as_uuid=True), ForeignKey("schemas.schema_id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String, nullable=False, default="PENDING")
    operation_type = Column(String, nullable=False)
    input_file_path = Column(String, nullable=True)
    output_file_path = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    schema = relationship("SchemaModel", back_populates="jobs")
