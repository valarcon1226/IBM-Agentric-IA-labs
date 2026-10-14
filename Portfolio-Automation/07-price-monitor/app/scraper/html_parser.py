"""HTML and JSON-LD product parser."""

import json
import logging
import re
from decimal import Decimal
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def clean_price_string(price_text: str) -> Decimal:
    """Extract a decimal number from a formatted price string.

    Handles formats like:
        $120.00 -> 120.00
        1.250,50 € -> 1250.50
        $ 85 -> 85.00
    """
    clean = price_text.strip()
    # Match digits, dots and commas
    # Remove any currency symbols or letters
    clean = re.sub(r"[^\d.,]", "", clean)

    if not clean:
        raise ValueError(f"No numeric price digits found in '{price_text}'")

    # If both dot and comma are present:
    # e.g. 1.250,50 (European) or 1,250.50 (US)
    if "." in clean and "," in clean:
        if clean.rfind(",") > clean.rfind("."):
            # European: 1.250,50 -> 1250.50
            clean = clean.replace(".", "").replace(",", ".")
        else:
            # US: 1,250.50 -> 1250.50
            clean = clean.replace(",", "")
    elif "," in clean:
        # Only comma: e.g. 1250,50 or 12,50
        parts = clean.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            clean = f"{parts[0]}.{parts[1]}"
        else:
            clean = clean.replace(",", "")

    return Decimal(clean)


def parse_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Find and parse JSON-LD Product/Offer schemas."""
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
        except (json.JSONDecodeError, TypeError):
            continue

        # Data could be a list, an @graph dictionary, or a direct Product dict
        candidates = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                candidates = data["@graph"]
            else:
                candidates = [data]

        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            # Check for "Product"
            if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
                name = item.get("name")
                offers = item.get("offers")
                if offers:
                    # Offers can be a dict or list
                    offer = offers[0] if isinstance(offers, list) and offers else offers
                    if isinstance(offer, dict) and "price" in offer:
                        price = clean_price_string(str(offer["price"]))
                        currency = offer.get("priceCurrency", "USD")
                        availability_str = str(offer.get("availability", ""))
                        availability = (
                            "InStock" in availability_str
                            or "instock" in availability_str.lower()
                            or not availability_str
                        )
                        return {
                            "title": name or "Unnamed Product",
                            "price": price,
                            "currency": currency,
                            "availability": availability,
                        }
    return None


def parse_css_selectors(
    soup: BeautifulSoup, selectors: dict[str, str] | None = None
) -> dict[str, Any] | None:
    """Extract product title and price using CSS selectors."""
    selectors = selectors or {}
    price_selector = (
        selectors.get("price") or "#product-price, .product-price, .price, [data-price]"
    )
    title_selector = selectors.get("title") or "#product-title, .product-title, h1"
    avail_selector = selectors.get("availability") or "#product-availability, .availability"

    price_elem = soup.select_one(price_selector)
    if not price_elem:
        return None

    raw_price = price_elem.get_text()
    price = clean_price_string(raw_price)

    # Check for currency attribute
    currency = price_elem.get("data-currency") or "USD"

    title_elem = soup.select_one(title_selector)
    title = title_elem.get_text().strip() if title_elem else "Scraped Product"

    availability = True
    avail_elem = soup.select_one(avail_selector)
    if avail_elem:
        text = avail_elem.get_text().lower()
        if "out of stock" in text or "agotado" in text or "no disponible" in text:
            availability = False

    return {
        "title": title,
        "price": price,
        "currency": currency,
        "availability": availability,
    }


def parse_product_html(
    html_content: str, css_selectors: dict[str, str] | None = None
) -> dict[str, Any]:
    """Parse product data from HTML: checks JSON-LD first, then falls back to CSS selectors."""
    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Try JSON-LD first (semantic, standardized)
    data = parse_json_ld(soup)
    if data:
        return data

    # 2. Fall back to CSS selectors
    data = parse_css_selectors(soup, selectors=css_selectors)
    if data:
        return data

    raise ValueError("Could not extract price or product information from HTML")
