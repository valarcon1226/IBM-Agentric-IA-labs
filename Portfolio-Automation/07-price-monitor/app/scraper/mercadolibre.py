"""MercadoLibre public API fetcher and parser."""

import re
from decimal import Decimal
from typing import Any

from app.scraper.fetching import PoliteFetcher


def extract_mercadolibre_item_id(url_or_id: str) -> str:
    """Extract item ID (e.g. MLA123456789) from a MercadoLibre URL or raw ID."""
    clean = url_or_id.strip()
    # Match patterns like MLA-123456789 or MLA123456789 or MLB123456789
    match = re.search(r"([A-Z]{3})-?([0-9]+)", clean)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    raise ValueError(f"Could not extract MercadoLibre item ID from: {url_or_id}")


def parse_mercadolibre_item_data(data: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON item payload returned by api.mercadolibre.com/items/{id}."""
    title = data.get("title") or "Unknown Product"
    raw_price = data.get("price")
    if raw_price is None:
        raise ValueError("MercadoLibre item data missing 'price' field")

    price = Decimal(str(raw_price))
    currency = data.get("currency_id") or "USD"
    status = data.get("status")
    available_qty = data.get("available_quantity", 0)
    availability = status == "active" and (available_qty is None or available_qty > 0)

    # Shipping and warranty metadata
    shipping = data.get("shipping", {})
    free_shipping = shipping.get("free_shipping", False)
    shipping_info = "Free Shipping" if free_shipping else None

    seller_address = data.get("seller_address", {})
    city_name = seller_address.get("city", {}).get("name")
    seller_reputation = f"City: {city_name}" if city_name else None

    return {
        "title": title,
        "price": price,
        "currency": currency,
        "availability": availability,
        "seller_reputation": seller_reputation,
        "shipping_info": shipping_info,
    }


def fetch_mercadolibre_product(url_or_id: str, fetcher: PoliteFetcher) -> dict[str, Any]:
    """Fetch product details via the official MercadoLibre public API."""
    item_id = extract_mercadolibre_item_id(url_or_id)
    api_url = f"https://api.mercadolibre.com/items/{item_id}"
    response = fetcher.get(api_url)
    data = response.json()
    return parse_mercadolibre_item_data(data)
