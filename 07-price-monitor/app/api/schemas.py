"""Pydantic schemas for request and response models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    name: str = Field(..., max_length=255, description="Product display name")
    url: str = Field(..., description="Product page or API URL")
    site_domain: str = Field(
        ..., max_length=100, description="Domain identifier, e.g. mercadolibre, demo-store"
    )
    css_selectors: dict[str, Any] | None = Field(
        default=None, description="Custom CSS selectors for scraping"
    )
    target_price: Decimal | None = Field(
        default=None, description="Target price to trigger alert when met or beaten"
    )
    alert_threshold_pct: Decimal = Field(
        default=Decimal("5.00"), description="Percentage price drop to trigger alert"
    )
    alert_threshold_abs: Decimal = Field(
        default=Decimal("0.00"), description="Absolute price drop to trigger alert"
    )
    currency: str = Field(
        default="USD", max_length=10, description="Currency code (USD, EUR, ARS, etc.)"
    )
    check_interval_hours: int = Field(
        default=6, ge=1, description="Interval in hours between checks"
    )
    requires_js: bool = Field(
        default=False, description="Whether JavaScript rendering via Playwright is required"
    )
    is_active: bool = Field(default=True, description="Whether monitoring is active")

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    target_price: Decimal | None = None
    alert_threshold_pct: Decimal | None = None
    alert_threshold_abs: Decimal | None = None
    currency: str | None = None
    check_interval_hours: int | None = Field(default=None, ge=1)
    requires_js: bool | None = None
    is_active: bool | None = None
    css_selectors: dict[str, Any] | None = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    last_scraped_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PriceHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    price: Decimal
    currency: str
    availability: bool
    rating: Decimal | None = None
    reviews_count: int | None = None
    seller_reputation: str | None = None
    shipping_info: str | None = None
    screenshot_path: str | None = None
    scraped_at: datetime


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    old_price: Decimal | None
    new_price: Decimal
    alert_type: str
    status: str
    sent_at: datetime


class ScrapeTriggerResponse(BaseModel):
    status: str
    product_id: str
    old_price: float | None = None
    new_price: float | None = None
    alert_triggered: bool = False
    error: str | None = None
