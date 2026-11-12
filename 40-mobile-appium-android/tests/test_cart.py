"""Shopping cart interactions and badge counter tests."""

from __future__ import annotations

import pytest

from screens.cart_screen import CartScreen
from screens.catalog_screen import CatalogScreen
from screens.navigation_header import NavigationHeader
from screens.product_detail_screen import ProductDetailScreen


@pytest.mark.cart
def test_add_to_cart_and_verify_counter(driver) -> None:
    """Scenario 4: Add an item to cart and assert the header badge counter updates."""
    catalog = CatalogScreen(driver)
    detail = ProductDetailScreen(driver)
    header = NavigationHeader(driver)

    assert catalog.is_loaded(), "Catalog should be loaded"
    initial_badge = header.get_cart_badge_count()

    catalog.open_first_product()
    assert detail.is_loaded(), "Product detail screen should load"

    detail.add_to_cart()

    updated_badge = header.get_cart_badge_count()
    assert updated_badge == initial_badge + 1, (
        f"Cart badge count expected {initial_badge + 1}, got {updated_badge}"
    )


@pytest.mark.cart
def test_remove_from_cart(driver) -> None:
    """Scenario 5: Remove an item from the shopping cart and verify empty state."""
    catalog = CatalogScreen(driver)
    detail = ProductDetailScreen(driver)
    header = NavigationHeader(driver)
    cart = CartScreen(driver)

    # 1. Add item to cart first to ensure test isolation
    assert catalog.is_loaded(), "Catalog should be loaded"
    catalog.open_first_product()
    assert detail.is_loaded(), "Product detail screen should load"
    detail.add_to_cart()

    # 2. Open cart and verify item presence
    header.open_cart()
    assert cart.is_loaded(), "Cart screen failed to load"
    assert cart.has_items(), "Cart should contain added item before removal"

    # 3. Remove the item
    cart.remove_first_item()

    # 4. Verify cart becomes empty
    assert cart.is_empty(), "Cart should display empty state after item removal"
    assert header.get_cart_badge_count() == 0, "Cart badge counter should be 0 when empty"
