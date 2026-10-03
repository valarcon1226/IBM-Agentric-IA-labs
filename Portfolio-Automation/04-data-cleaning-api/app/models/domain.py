from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    """Public view of a persisted job."""

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: str
    operation_type: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
