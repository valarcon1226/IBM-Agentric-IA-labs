"""Product CRUD, history, and scrape triggering routes."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_session
from app.api.schemas import (
    PriceHistoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ScrapeTriggerResponse,
)
from app.db.models import PriceHistory, Product
from app.workers.tasks import run_scrape

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Register a new product for price monitoring."""
    # Check if URL already registered
    existing = await session.scalar(select(Product).where(Product.url == payload.url))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with URL '{payload.url}' is already registered.",
        )

    product = Product(**payload.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@router.get("/", response_model=list[ProductResponse])
async def list_products(
    is_active: bool | None = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """List all registered products."""
    stmt = select(Product).order_by(Product.created_at.desc())
    if is_active is not None:
        stmt = stmt.where(Product.is_active == is_active)
    result = await session.scalars(stmt)
    return result.all()


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Get a single product by ID."""
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Update fields of an existing product."""
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(product, field, val)

    await session.commit()
    await session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Delete a product and its associated price history and alerts."""
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )

    await session.delete(product)
    await session.commit()
    return {"message": "Product deleted successfully."}


@router.post("/{product_id}/scrape", response_model=ScrapeTriggerResponse)
async def trigger_scrape(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Trigger an immediate scrape for a specific product."""
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )

    # Execute scrape synchronously to return immediate result to caller
    result = run_scrape(str(product_id))
    return ScrapeTriggerResponse(
        status=result.get("status", "UNKNOWN"),
        product_id=str(product_id),
        old_price=result.get("old_price"),
        new_price=result.get("new_price"),
        alert_triggered=result.get("alert_triggered", False),
        error=result.get("error"),
    )


@router.get("/{product_id}/history", response_model=list[PriceHistoryResponse])
async def get_price_history(
    product_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000, description="Max history points to return"),
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """Get chronological price history for a product."""
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )

    stmt = (
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.scraped_at.asc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return result.all()
