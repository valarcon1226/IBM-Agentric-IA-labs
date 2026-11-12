"""Pydantic schemas for HTTP requests and responses."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LineItemSchema(BaseModel):
    item_id: uuid.UUID | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    invoice_id: uuid.UUID
    original_filename: str
    minio_key: str
    issuer_name: str | None = None
    issuer_vat: str | None = None
    recipient_name: str | None = None
    recipient_vat: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    is_valid: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    status: str = "COMPLETED"
    created_at: datetime
    line_items: list[LineItemSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InvoiceListItem(BaseModel):
    invoice_id: uuid.UUID
    issuer_name: str | None = None
    total: Decimal | None = None
    currency: str | None = None
    is_valid: bool = False
    status: str = "COMPLETED"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    data: list[InvoiceListItem]
    total_records: int
    page: int
    limit: int


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: str | None = None
    message: str | None = None
    invoice_id: uuid.UUID | None = None


class ExportRequest(BaseModel):
    format: str = "csv"
    start_date: date | None = None
    end_date: date | None = None


class ExportResponse(BaseModel):
    status: str = "SUCCESS"
    exported_records: int
    format: str
    content: str | None = None
