"""Celery tasks for scraping products and periodic checks."""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.models import PriceHistory, Product, ScrapingLog
from app.db.session import get_sync_session
from app.scraper.alerts import evaluate_and_dispatch_alert
from app.scraper.edge_fetcher import fetch_with_edge
from app.scraper.fetching import PoliteFetcher, RobotsDisallowed
from app.scraper.html_parser import parse_product_html
from app.scraper.mercadolibre import fetch_mercadolibre_product
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_scrape(product_id: uuid.UUID | str) -> dict[str, Any]:
    """Execute scraping logic for a single product."""
    if isinstance(product_id, str):
        product_uuid = uuid.UUID(product_id)
    else:
        product_uuid = product_id

    with get_sync_session() as session:
        product = session.get(Product, product_uuid)
        if not product:
            logger.error("Product with id %s not found", product_uuid)
            return {"status": "NOT_FOUND"}

        # Get latest previous price
        stmt = (
            select(PriceHistory.price)
            .where(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.scraped_at.desc())
            .limit(1)
        )
        old_price: Decimal | None = session.scalar(stmt)

        now = datetime.now(UTC)
        with PoliteFetcher() as fetcher:
            try:
                # 1. MercadoLibre API vs Custom/Demo HTML
                is_ml = (
                    "mercadolibre" in product.site_domain.lower()
                    or "mercadolibre" in product.url.lower()
                )

                if is_ml:
                    parsed_data = fetch_mercadolibre_product(product.url, fetcher)
                else:
                    if product.requires_js:
                        html_content = fetch_with_edge(product.url, user_agent=fetcher.user_agent)
                    else:
                        response = fetcher.get(product.url)
                        html_content = response.text

                    parsed_data = parse_product_html(
                        html_content, css_selectors=product.css_selectors
                    )

                new_price = parsed_data["price"]
                currency = parsed_data.get("currency") or product.currency
                availability = parsed_data.get("availability", True)

                # Record price history
                history = PriceHistory(
                    product_id=product.id,
                    price=new_price,
                    currency=currency,
                    availability=availability,
                    rating=parsed_data.get("rating"),
                    reviews_count=parsed_data.get("reviews_count"),
                    seller_reputation=parsed_data.get("seller_reputation"),
                    shipping_info=parsed_data.get("shipping_info"),
                    scraped_at=now,
                )
                session.add(history)

                # Check alerts
                alert = evaluate_and_dispatch_alert(
                    session=session,
                    product=product,
                    new_price=new_price,
                    old_price=old_price,
                )

                # Update product last_scraped_at
                product.last_scraped_at = now

                # Log scraping success
                log = ScrapingLog(
                    product_id=product.id,
                    status="SUCCESS",
                    executed_at=now,
                )
                session.add(log)

                return {
                    "status": "SUCCESS",
                    "product_id": str(product.id),
                    "old_price": float(old_price) if old_price is not None else None,
                    "new_price": float(new_price),
                    "alert_triggered": alert is not None,
                }

            except RobotsDisallowed as exc:
                logger.warning("Scrape blocked by robots.txt for product %s: %s", product.id, exc)
                log = ScrapingLog(
                    product_id=product.id,
                    status="ROBOTS_DISALLOWED",
                    error_message=str(exc),
                    executed_at=now,
                )
                session.add(log)
                return {"status": "ROBOTS_DISALLOWED", "error": str(exc)}

            except Exception as exc:
                logger.error("Scraping failed for product %s: %s", product.id, exc, exc_info=True)
                log = ScrapingLog(
                    product_id=product.id,
                    status="ERROR",
                    error_message=str(exc),
                    executed_at=now,
                )
                session.add(log)
                return {"status": "ERROR", "error": str(exc)}


@celery_app.task(name="app.workers.tasks.scrape_product")
def scrape_product(product_id: str) -> dict[str, Any]:
    """Celery task to scrape a single product."""
    return run_scrape(product_id)


@celery_app.task(name="app.workers.tasks.check_all_active_products")
def check_all_active_products() -> dict[str, Any]:
    """Celery beat task to enqueue scraping jobs for all active products."""
    with get_sync_session() as session:
        stmt = select(Product.id).where(Product.is_active == True)  # noqa: E712
        product_ids = session.scalars(stmt).all()

    enqueued = 0
    for pid in product_ids:
        scrape_product.delay(str(pid))
        enqueued += 1

    logger.info("Enqueued scrape tasks for %d active products", enqueued)
    return {"enqueued": enqueued}
