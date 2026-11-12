"""Screen Object for the main Product Catalog."""

from __future__ import annotations

import re

from appium.webdriver.common.appiumby import AppiumBy

from screens.base_screen import BaseScreen


class CatalogScreen(BaseScreen):
    """Product catalog grid view displayed upon application launch."""

    CATALOG_TITLE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productTV")
    CATALOG_GRID = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productRV")
    PRODUCT_IMAGE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productIV")
    PRODUCT_TITLE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/titleTV")
    PRODUCT_PRICE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/priceTV")

    def is_loaded(self) -> bool:
        """Verify catalog title and product grid are visible."""
        return (
            self.is_displayed(*self.CATALOG_TITLE, timeout=10.0)
            and self.is_displayed(*self.CATALOG_GRID, timeout=10.0)
        )

    def get_title_text(self) -> str:
        """Return the catalog header title."""
        return self.get_text(*self.CATALOG_TITLE)

    def get_product_titles(self) -> list[str]:
        """Return text of currently visible product titles."""
        elements = self.find_all(*self.PRODUCT_TITLE, timeout=5.0)
        return [el.text.strip() for el in elements if el.text.strip()]

    def get_product_prices(self) -> list[float]:
        """Extract and parse numeric prices of visible products (e.g. '$ 29.99' -> 29.99)."""
        elements = self.find_all(*self.PRODUCT_PRICE, timeout=5.0)
        prices: list[float] = []
        for el in elements:
            cleaned = re.sub(r"[^\d.]", "", el.text)
            if cleaned:
                prices.append(float(cleaned))
        return prices

    def open_product_by_index(self, index: int = 0) -> None:
        """Tap product card/image at the specified index to open detail view."""
        images = self.find_all(*self.PRODUCT_IMAGE, timeout=5.0)
        if not images:
            raise RuntimeError("No products found in catalog grid to open.")
        if index >= len(images):
            raise IndexError(f"Product index {index} out of range ({len(images)} visible).")
        images[index].click()

    def open_first_product(self) -> None:
        """Convenience helper to tap the very first visible product."""
        self.open_product_by_index(0)
