"""SQLAlchemy ORM models for Price Monitor."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, index=True, nullable=False)
    site_domain: Mapped[str] = mapped_column(String(100), nullable=False)
    css_selectors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    alert_threshold_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("5.00"), nullable=False
    )
    alert_threshold_abs: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    check_interval_hours: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    requires_js: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="product", cascade="all, delete-orphan"
    )
    scraping_logs: Mapped[list["ScrapingLog"]] = relationship(
        "ScrapingLog", back_populates="product", cascade="all, delete-orphan"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    availability: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_reputation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shipping_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    product: Mapped["Product"] = relationship("Product", back_populates="price_history")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    new_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product: Mapped["Product"] = relationship("Product", back_populates="alerts")


class ScrapingLog(Base):
    __tablename__ = "scraping_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    product: Mapped["Product"] = relationship("Product", back_populates="scraping_logs")
