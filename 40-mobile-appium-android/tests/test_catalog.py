"""Catalog and product navigation tests."""

from __future__ import annotations

import pytest

from screens.catalog_screen import CatalogScreen
from screens.navigation_header import NavigationHeader
from screens.product_detail_screen import ProductDetailScreen
from screens.sort_dialog import SortDialog


@pytest.mark.catalog
def test_catalog_visible_on_open(driver) -> None:
    """Scenario 1: Catalog screen displays upon opening the application."""
    catalog = CatalogScreen(driver)

    assert catalog.is_loaded(), "Product Catalog screen failed to load upon app launch"
    assert catalog.get_title_text() == "Products", (
        "Catalog title does not match expected 'Products'"
    )

    titles = catalog.get_product_titles()
    assert len(titles) > 0, "Expected at least one product card to be displayed in catalog"


@pytest.mark.catalog
def test_sort_catalog_by_price(driver) -> None:
    """Scenario 2: Sort product catalog by price ascending and verify items reorder."""
    catalog = CatalogScreen(driver)
    header = NavigationHeader(driver)
    sort_dialog = SortDialog(driver)

    assert catalog.is_loaded(), "Catalog should be loaded before sorting"

    header.open_sort_dialog()
    sort_dialog.sort_by_price_ascending()

    prices = catalog.get_product_prices()
    assert len(prices) >= 2, f"Expected at least 2 prices to verify sorting, found {len(prices)}"
    assert prices == sorted(prices), (
        f"Product prices are not sorted in ascending order: {prices}"
    )


@pytest.mark.catalog
def test_open_product_detail(driver) -> None:
    """Scenario 3: Open product detail view from catalog and verify item information."""
    catalog = CatalogScreen(driver)
    detail = ProductDetailScreen(driver)

    assert catalog.is_loaded(), "Catalog should be loaded before selecting product"

    catalog_titles = catalog.get_product_titles()
    assert len(catalog_titles) > 0, "No products available in catalog"
    expected_title = catalog_titles[0]

    catalog.open_first_product()

    assert detail.is_loaded(), "Product detail screen failed to load"
    assert detail.get_title() == expected_title, (
        f"Detail title '{detail.get_title()}' does not match catalog title '{expected_title}'"
    )
    assert detail.get_price() > 0.0, "Product price should be greater than zero"
    assert detail.get_quantity() == 1, "Initial product quantity should default to 1"
