from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class RowData(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""


class UploadResponse(BaseModel):
    upload_id: UUID
    status: str
    message: str


class StatusResponse(BaseModel):
    upload_id: UUID
    status: str
    total_rows: int | None
    clean_rows: int
    ambiguous_rows: int
    failed_rows: int


class ReviewItem(BaseModel):
    record_id: UUID
    upload_id: UUID
    line_number: int
    data: RowData
    reasons: list[str]


class ReviewResponse(BaseModel):
    upload_id: UUID
    pending_reviews: list[ReviewItem]


class ReviewRequest(BaseModel):
    record_id: UUID
    action: Literal["approve", "reject"]
    corrected_data: RowData | None = None


class ReviewResult(BaseModel):
    status: str
    message: str
