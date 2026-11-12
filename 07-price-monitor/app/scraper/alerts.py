"""Price threshold evaluation and webhook alerting."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Alert, Product

logger = logging.getLogger(__name__)


def evaluate_and_dispatch_alert(
    session: Session,
    product: Product,
    new_price: Decimal,
    old_price: Decimal | None,
) -> Alert | None:
    """Evaluate whether price changes meet alert thresholds and send a webhook notification."""
    alert_type: str | None = None
    reason: str | None = None

    # Condition 1: Target price met
    if product.target_price is not None and new_price <= product.target_price:
        alert_type = "TARGET_PRICE_MET"
        reason = f"Price {new_price} is at or below target price of {product.target_price}"

    # Condition 2: Percentage threshold breached
    elif old_price is not None and old_price > 0 and product.alert_threshold_pct is not None:
        pct_change = abs(float(new_price) - float(old_price)) / float(old_price) * 100.0
        if pct_change >= float(product.alert_threshold_pct):
            alert_type = "PRICE_CHANGE_PCT"
            direction = "dropped" if new_price < old_price else "increased"
            reason = (
                f"Price {direction} by {pct_change:.2f}% (from {old_price} to {new_price}), "
                f"exceeding threshold of {product.alert_threshold_pct}%"
            )

    # Condition 3: Absolute threshold breached
    elif (
        old_price is not None
        and product.alert_threshold_abs is not None
        and product.alert_threshold_abs > 0
    ):
        diff = abs(new_price - old_price)
        if diff >= product.alert_threshold_abs:
            alert_type = "PRICE_CHANGE_ABS"
            direction = "dropped" if new_price < old_price else "increased"
            reason = (
                f"Price {direction} by {diff} (from {old_price} to {new_price}), "
                f"exceeding threshold of {product.alert_threshold_abs}"
            )

    if not alert_type or not reason:
        return None

    # Dispatch webhook
    webhook_url = settings.WEBHOOK_ALERT_URL
    payload = {
        "event": "PRICE_ALERT",
        "product_id": str(product.id),
        "product_name": product.name,
        "url": product.url,
        "old_price": float(old_price) if old_price is not None else None,
        "new_price": float(new_price),
        "target_price": float(product.target_price) if product.target_price is not None else None,
        "currency": product.currency,
        "alert_type": alert_type,
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    status_str = "SENT"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(webhook_url, json=payload)
            if resp.status_code >= 400:
                logger.error(
                    "Webhook sink responded with status %d: %s", resp.status_code, resp.text
                )
                status_str = "FAILED"
    except Exception as exc:
        logger.error("Failed to dispatch alert webhook to %s: %s", webhook_url, exc)
        status_str = "FAILED"

    alert = Alert(
        product_id=product.id,
        old_price=old_price,
        new_price=new_price,
        alert_type=alert_type,
        status=status_str,
        sent_at=datetime.now(UTC),
    )
    session.add(alert)
    session.flush()

    logger.info("Alert %s created for product %s (%s)", alert_type, product.name, status_str)
    return alert
