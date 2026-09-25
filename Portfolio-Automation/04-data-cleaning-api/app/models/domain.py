from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CleanOptions(BaseModel):
    """Options for data cleaning."""

    remove_duplicates: bool = False
    fill_na: str | None = None
    trim_whitespace: bool = False


class ValidateRequest(BaseModel):
    """Request schema for data validation."""

    schema_id: UUID
    data: list[dict[str, Any]]


class ValidateResponse(BaseModel):
    """Response schema for data validation."""

    is_valid: bool
    errors: list[str] = []
    validated_rows: int


class TransformRequest(BaseModel):
    """Request schema for data transformation."""

    operation: str
    index: str | None = None
    columns: str | None = None
    values: str | None = None
    data_url: str


class EnrichRequest(BaseModel):
    """Request schema for data enrichment."""

    operations: list[str]
    target_columns: dict[str, str]
    data_url: str


class JobResponse(BaseModel):
    """Response schema for a job."""

    job_id: UUID
    status: str
    operation_type: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class JobResultResponse(BaseModel):
    """Response schema for job results."""

    job_id: UUID
    download_url: str
    expires_in: int


class SchemaCreate(BaseModel):
    """Request schema for creating a schema."""

    name: str
    definition: dict[str, Any]


class SchemaResponse(BaseModel):
    """Response schema for a schema."""

    schema_id: UUID
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class SchemaListResponse(BaseModel):
    """Response schema for listing schemas."""

    schemas: list[SchemaResponse]
    total: int
