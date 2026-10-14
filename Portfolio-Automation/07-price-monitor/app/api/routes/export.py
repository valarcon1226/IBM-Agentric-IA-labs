"""CSV Export route for price history."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_session
from app.db.models import PriceHistory, Product

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/csv")
async def export_price_history_csv(
    product_id: uuid.UUID | None = Query(None, description="Filter history by product ID"),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Export product price history as a CSV file download."""
    stmt = (
        select(
            PriceHistory.scraped_at,
            Product.name.label("product_name"),
            Product.url,
            PriceHistory.price,
            PriceHistory.currency,
            PriceHistory.availability,
            Product.id.label("product_id"),
        )
        .join(Product, PriceHistory.product_id == Product.id)
        .order_by(PriceHistory.scraped_at.desc())
    )

    if product_id is not None:
        stmt = stmt.where(PriceHistory.product_id == product_id)

    result = await session.execute(stmt)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "scraped_at",
            "product_id",
            "product_name",
            "url",
            "price",
            "currency",
            "availability",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.scraped_at.isoformat() if row.scraped_at else "",
                str(row.product_id),
                row.product_name,
                row.url,
                str(row.price),
                row.currency,
                "true" if row.availability else "false",
            ]
        )

    csv_data = output.getvalue()
    filename = f"price_history_{product_id}.csv" if product_id else "price_history_all.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
