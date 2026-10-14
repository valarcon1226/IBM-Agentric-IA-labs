"""Pydantic models for API request and response bodies."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_serializer


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nombre de la fuente")
    url: str = Field(..., min_length=5, pattern=r"^https?://", description="URL http(s) del feed RSS o sitio web")
    source_type: str = Field(default="RSS", description="Tipo de fuente: RSS o SCRAPE")
    is_active: bool = Field(default=True, description="Estado activo para ingesta")


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    url: str | None = Field(default=None, min_length=5, pattern=r"^https?://")
    source_type: str | None = None
    is_active: bool | None = None


class SourceResponse(BaseModel):
    id: str | uuid.UUID
    name: str
    url: str
    source_type: str
    is_active: bool
    health_status: str
    last_fetched_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime

    @field_serializer("id")
    def serialize_id(self, v: str | uuid.UUID) -> str:
        return str(v)


class ArticleResponse(BaseModel):
    id: str | uuid.UUID
    title: str
    url: str
    author: str | None = None
    published_date: datetime | None = None
    ai_summary: str | None = None
    category: str | None = None
    source_name: str | None = None
    is_duplicate: bool = False
    parent_article_id: str | uuid.UUID | None = None
    created_at: datetime

    @field_serializer("id", "parent_article_id")
    def serialize_uuid(self, v: str | uuid.UUID | None) -> str | None:
        return str(v) if v is not None else None


class DigestGenerateRequest(BaseModel):
    target_audience: str = Field(default="TEAM_DIGEST", description="Audiencia objetivo")
    recipient_email: str | None = Field(default=None, description="Correo receptor opcional")
    category: str | None = Field(default=None, description="Filtrar por categoría opcional")


class DigestResponse(BaseModel):
    id: str | uuid.UUID
    target_audience: str
    recipient_email: str | None = None
    sent_at: datetime
    status: str
    article_count: int
    error_message: str | None = None

    @field_serializer("id")
    def serialize_id(self, v: str | uuid.UUID) -> str:
        return str(v)


class IngestResponse(BaseModel):
    message: str
    processed_sources: int
    total_articles: int
    new_articles: int
    duplicates_detected: int
