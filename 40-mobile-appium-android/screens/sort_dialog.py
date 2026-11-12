"""Screen Object for the Catalog Sort modal dialog."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from screens.base_screen import BaseScreen


class SortDialog(BaseScreen):
    """Sort options modal dialog."""

    PRICE_ASC = (AppiumBy.ACCESSIBILITY_ID, "Ascending order by price")
    PRICE_ASC_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/priceAscCL")

    PRICE_DESC = (AppiumBy.ACCESSIBILITY_ID, "Descending order by price")
    PRICE_DESC_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/priceDesCL")

    NAME_ASC = (AppiumBy.ACCESSIBILITY_ID, "Ascending order by name")
    NAME_ASC_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/nameAscCL")

    NAME_DESC = (AppiumBy.ACCESSIBILITY_ID, "Descending order by name")
    NAME_DESC_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/nameDesCL")

    def sort_by_price_ascending(self) -> None:
        """Select ascending order by price option."""
        if self.is_displayed(*self.PRICE_ASC, timeout=2.0):
            self.click(*self.PRICE_ASC)
        else:
            self.click(*self.PRICE_ASC_FALLBACK)

    def sort_by_price_descending(self) -> None:
        """Select descending order by price option."""
        if self.is_displayed(*self.PRICE_DESC, timeout=2.0):
            self.click(*self.PRICE_DESC)
        else:
            self.click(*self.PRICE_DESC_FALLBACK)

    def sort_by_name_ascending(self) -> None:
        """Select ascending order by name option."""
        if self.is_displayed(*self.NAME_ASC, timeout=2.0):
            self.click(*self.NAME_ASC)
        else:
            self.click(*self.NAME_ASC_FALLBACK)

    def sort_by_name_descending(self) -> None:
        """Select descending order by name option."""
        if self.is_displayed(*self.NAME_DESC, timeout=2.0):
            self.click(*self.NAME_DESC)
        else:
            self.click(*self.NAME_DESC_FALLBACK)
