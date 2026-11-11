"""Screen Object for the Cart screen."""

from __future__ import annotations

import re

from appium.webdriver.common.appiumby import AppiumBy

from screens.base_screen import BaseScreen


class CartScreen(BaseScreen):
    """Shopping cart screen managing item rows, totals, and removal."""

    CART_TITLE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productTV")
    CART_RECYCLER = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productRV")
    ITEMS_TOTAL_LABEL = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/itemsTV")
    TOTAL_PRICE_LABEL = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/totalPriceTV")

    # Item row controls
    REMOVE_ITEM_BUTTON = (AppiumBy.ACCESSIBILITY_ID, "Removes product from cart")
    REMOVE_ITEM_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/removeBt")

    # Empty cart state
    EMPTY_CART_TITLE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/noItemTitleTV")
    GO_SHOPPING_BUTTON = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/shoppingBt")

    def is_loaded(self) -> bool:
        """Verify cart screen has finished loading (either empty or populated)."""
        return self.is_displayed(*self.CART_TITLE, timeout=8.0) or self.is_displayed(
            *self.EMPTY_CART_TITLE, timeout=8.0
        )

    def is_empty(self) -> bool:
        """Check whether the empty state message ('No Items') is displayed."""
        return self.is_displayed(*self.EMPTY_CART_TITLE, timeout=5.0)

    def has_items(self) -> bool:
        """Check whether at least one cart item row is present."""
        return self.is_displayed(*self.REMOVE_ITEM_FALLBACK, timeout=3.0) or self.is_displayed(
            *self.REMOVE_ITEM_BUTTON, timeout=3.0
        )

    def get_items_summary_text(self) -> str:
        """Return text like '1 items'."""
        if not self.is_displayed(*self.ITEMS_TOTAL_LABEL, timeout=3.0):
            return "0 items"
        return self.get_text(*self.ITEMS_TOTAL_LABEL)

    def get_total_price(self) -> float:
        """Return total price as a float."""
        if not self.is_displayed(*self.TOTAL_PRICE_LABEL, timeout=3.0):
            return 0.0
        raw = self.get_text(*self.TOTAL_PRICE_LABEL)
        cleaned = re.sub(r"[^\d.]", "", raw)
        return float(cleaned) if cleaned else 0.0

    def remove_first_item(self) -> None:
        """Click the remove item button on the first row."""
        if self.is_displayed(*self.REMOVE_ITEM_BUTTON, timeout=3.0):
            self.click(*self.REMOVE_ITEM_BUTTON)
        else:
            self.click(*self.REMOVE_ITEM_FALLBACK)

    def go_shopping(self) -> None:
        """Click 'Go Shopping' button in empty cart state."""
        self.click(*self.GO_SHOPPING_BUTTON)
