"""Alert retrieval routes."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_session
from app.api.schemas import AlertResponse
from app.db.models import Alert, Product

router = APIRouter(tags=["alerts"])


@router.get("/alerts/", response_model=list[AlertResponse])
async def list_alerts(
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """List recent price alerts across all products."""
    stmt = select(Alert).order_by(Alert.sent_at.desc()).limit(limit)
    result = await session.scalars(stmt)
    return result.all()


@router.get("/products/{product_id}/alerts", response_model=list[AlertResponse])
async def list_product_alerts(
    product_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """List alerts triggered for a specific product."""
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )

    stmt = (
        select(Alert)
        .where(Alert.product_id == product_id)
        .order_by(Alert.sent_at.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return result.all()
