"""Screen Object for Product Detail screen."""

from __future__ import annotations

import re

from appium.webdriver.common.appiumby import AppiumBy

from screens.base_screen import BaseScreen


class ProductDetailScreen(BaseScreen):
    """Product detail view showing specs, quantity, and add-to-cart action."""

    PRODUCT_TITLE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productTV")
    PRODUCT_PRICE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/priceTV")
    QUANTITY_LABEL = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/noTV")
    INCREASE_QTY = (AppiumBy.ACCESSIBILITY_ID, "Increase item quantity")
    INCREASE_QTY_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/plusIV")
    DECREASE_QTY = (AppiumBy.ACCESSIBILITY_ID, "Decrease item quantity")
    DECREASE_QTY_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/minusIV")
    ADD_TO_CART_BUTTON = (AppiumBy.ACCESSIBILITY_ID, "Tap to add product to cart")
    ADD_TO_CART_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartBt")
    HIGHLIGHTS_TITLE = (
        AppiumBy.ID,
        "com.saucelabs.mydemoapp.android:id/productHeightLightsTV",
    )

    def is_loaded(self) -> bool:
        """Verify product detail elements are visible."""
        return (
            self.is_displayed(*self.PRODUCT_TITLE, timeout=8.0)
            and self.is_displayed(*self.PRODUCT_PRICE, timeout=8.0)
            and (
                self.is_displayed(*self.ADD_TO_CART_BUTTON, timeout=2.0)
                or self.is_displayed(*self.ADD_TO_CART_FALLBACK, timeout=2.0)
            )
        )

    def get_title(self) -> str:
        """Return the product title."""
        return self.get_text(*self.PRODUCT_TITLE)

    def get_price(self) -> float:
        """Return numeric price as a float."""
        raw = self.get_text(*self.PRODUCT_PRICE)
        cleaned = re.sub(r"[^\d.]", "", raw)
        return float(cleaned) if cleaned else 0.0

    def get_quantity(self) -> int:
        """Return current quantity selected."""
        raw = self.get_text(*self.QUANTITY_LABEL)
        return int(raw) if raw.isdigit() else 1

    def increase_quantity(self) -> None:
        """Click plus button to increase quantity."""
        if self.is_displayed(*self.INCREASE_QTY, timeout=2.0):
            self.click(*self.INCREASE_QTY)
        else:
            self.click(*self.INCREASE_QTY_FALLBACK)

    def add_to_cart(self) -> None:
        """Click 'Add to cart' button."""
        if self.is_displayed(*self.ADD_TO_CART_BUTTON, timeout=2.0):
            self.click(*self.ADD_TO_CART_BUTTON)
        else:
            self.click(*self.ADD_TO_CART_FALLBACK)
