"""Unit tests for HTML, JSON-LD, and MercadoLibre parsers."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.scraper.html_parser import clean_price_string, parse_product_html
from app.scraper.mercadolibre import (
    extract_mercadolibre_item_id,
    parse_mercadolibre_item_data,
)


def test_clean_price_string():
    assert clean_price_string("$120.00") == Decimal("120.00")
    assert clean_price_string("85.00 USD") == Decimal("85.00")
    assert clean_price_string("1.250,50 €") == Decimal("1250.50")
    assert clean_price_string("389,999.00") == Decimal("389999.00")
    assert clean_price_string("45") == Decimal("45")

    with pytest.raises(ValueError):
        clean_price_string("Free Item No Digits")


def test_parse_json_ld_keyboard(fixtures_dir: Path):
    html = (fixtures_dir / "demo_keyboard.html").read_text(encoding="utf-8")
    data = parse_product_html(html)

    assert data["title"] == "Mechanical Keyboard RGB"
    assert data["price"] == Decimal("120.00")
    assert data["currency"] == "USD"
    assert data["availability"] is True


def test_parse_json_ld_headphones(fixtures_dir: Path):
    html = (fixtures_dir / "demo_headphones.html").read_text(encoding="utf-8")
    data = parse_product_html(html)

    assert data["title"] == "Studio Monitor Headphones"
    assert data["price"] == Decimal("85.00")
    assert data["currency"] == "USD"
    assert data["availability"] is True


def test_parse_css_selectors_custom(fixtures_dir: Path):
    html = (fixtures_dir / "custom_css_product.html").read_text(encoding="utf-8")
    selectors = {
        "price": ".custom-price-tag",
        "title": ".item-name",
        "availability": ".stock-status",
    }
    data = parse_product_html(html, css_selectors=selectors)

    assert data["title"] == "Handmade Leather Bag"
    assert data["price"] == Decimal("249.50")
    assert data["availability"] is True


def test_parse_html_fails_without_price():
    empty_html = "<html><body><h1>No Price Here</h1></body></html>"
    with pytest.raises(ValueError, match="Could not extract price"):
        parse_product_html(empty_html)


def test_extract_mercadolibre_item_id():
    assert extract_mercadolibre_item_id("MLA123456789") == "MLA123456789"
    assert extract_mercadolibre_item_id("MLA-123456789") == "MLA123456789"
    assert (
        extract_mercadolibre_item_id(
            "https://articulo.mercadolibre.com.ar/MLA-123456789-auriculares-sony.html"
        )
        == "MLA123456789"
    )
    assert (
        extract_mercadolibre_item_id("https://api.mercadolibre.com/items/MLA987654321")
        == "MLA987654321"
    )

    with pytest.raises(ValueError):
        extract_mercadolibre_item_id("https://example.com/not-ml")


def test_parse_mercadolibre_item_data(fixtures_dir: Path):
    json_path = fixtures_dir / "mercadolibre_item_MLA12345.json"
    raw_data = json.loads(json_path.read_text(encoding="utf-8"))

    data = parse_mercadolibre_item_data(raw_data)
    assert data["title"] == "Auriculares Inalámbricos Sony Wh-1000xm5 Cancelación Ruido"
    assert data["price"] == Decimal("389999.00")
    assert data["currency"] == "ARS"
    assert data["availability"] is True
    assert data["shipping_info"] == "Free Shipping"
    assert "Capital Federal" in data["seller_reputation"]
