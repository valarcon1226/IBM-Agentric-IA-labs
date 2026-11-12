"""Unit tests for alert evaluation and webhook notifications."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.db.models import Product
from app.scraper.alerts import evaluate_and_dispatch_alert


def _make_product(
    target_price: Decimal | None = Decimal("100.00"),
    alert_threshold_pct: Decimal = Decimal("5.00"),
    alert_threshold_abs: Decimal = Decimal("0.00"),
) -> Product:
    return Product(
        id=uuid.uuid4(),
        name="Test Headphones",
        url="http://demo-store/products/headphones.html",
        site_domain="demo-store",
        target_price=target_price,
        alert_threshold_pct=alert_threshold_pct,
        alert_threshold_abs=alert_threshold_abs,
        currency="USD",
    )


def test_alert_triggers_when_target_price_met():
    product = _make_product(target_price=Decimal("100.00"))
    mock_session = MagicMock(spec=Session)

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        alert = evaluate_and_dispatch_alert(
            session=mock_session,
            product=product,
            new_price=Decimal("95.00"),
            old_price=Decimal("120.00"),
        )

        assert alert is not None
        assert alert.alert_type == "TARGET_PRICE_MET"
        assert alert.new_price == Decimal("95.00")
        assert alert.status == "SENT"
        mock_post.assert_called_once()
        mock_session.add.assert_called_once_with(alert)


def test_alert_triggers_on_percentage_drop():
    # Target price not met, but price dropped from 200 to 180 (10% drop, threshold is 5%)
    product = _make_product(target_price=Decimal("150.00"), alert_threshold_pct=Decimal("5.00"))
    mock_session = MagicMock(spec=Session)

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        alert = evaluate_and_dispatch_alert(
            session=mock_session,
            product=product,
            new_price=Decimal("180.00"),
            old_price=Decimal("200.00"),
        )

        assert alert is not None
        assert alert.alert_type == "PRICE_CHANGE_PCT"
        assert alert.status == "SENT"
        mock_post.assert_called_once()


def test_no_alert_when_thresholds_not_breached():
    # Target 100, threshold 10%, price moved from 120 to 118 (drop of 1.6%)
    product = _make_product(target_price=Decimal("100.00"), alert_threshold_pct=Decimal("10.00"))
    mock_session = MagicMock(spec=Session)

    with patch("httpx.Client.post") as mock_post:
        alert = evaluate_and_dispatch_alert(
            session=mock_session,
            product=product,
            new_price=Decimal("118.00"),
            old_price=Decimal("120.00"),
        )

        assert alert is None
        mock_post.assert_not_called()
        mock_session.add.assert_not_called()


def test_alert_records_failed_status_on_network_error():
    product = _make_product(target_price=Decimal("100.00"))
    mock_session = MagicMock(spec=Session)

    with patch("httpx.Client.post", side_effect=Exception("Connection refused")):
        alert = evaluate_and_dispatch_alert(
            session=mock_session,
            product=product,
            new_price=Decimal("80.00"),
            old_price=Decimal("120.00"),
        )

        assert alert is not None
        assert alert.status == "FAILED"
        mock_session.add.assert_called_once_with(alert)
