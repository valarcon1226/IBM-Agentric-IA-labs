"""Screen Object for top app header and navigation drawer."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from screens.base_screen import BaseScreen


class NavigationHeader(BaseScreen):
    """Header toolbar containing menu, sort, and cart actions."""

    MENU_BUTTON = (AppiumBy.ACCESSIBILITY_ID, "View menu")
    MENU_BUTTON_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV")
    SORT_BUTTON = (
        AppiumBy.ACCESSIBILITY_ID,
        "Shows current sorting order and displays available sorting options",
    )
    SORT_BUTTON_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/sortIV")
    CART_BUTTON = (AppiumBy.ACCESSIBILITY_ID, "View cart")
    CART_BUTTON_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartRL")
    CART_BADGE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartTV")

    # Drawer menu items
    DRAWER_MENU_CONTAINER = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuRV")
    LOGIN_MENU_ITEM = (AppiumBy.ACCESSIBILITY_ID, "Login Menu Item")
    LOGOUT_MENU_ITEM = (AppiumBy.ACCESSIBILITY_ID, "Logout Menu Item")

    def open_menu(self) -> None:
        """Open the navigation drawer."""
        if self.is_displayed(*self.MENU_BUTTON, timeout=2.0):
            self.click(*self.MENU_BUTTON)
        else:
            self.click(*self.MENU_BUTTON_FALLBACK)
        self.find(*self.DRAWER_MENU_CONTAINER)

    def open_sort_dialog(self) -> None:
        """Open the product sorting modal dialog."""
        if self.is_displayed(*self.SORT_BUTTON, timeout=2.0):
            self.click(*self.SORT_BUTTON)
        else:
            self.click(*self.SORT_BUTTON_FALLBACK)

    def open_cart(self) -> None:
        """Navigate to Cart screen."""
        if self.is_displayed(*self.CART_BUTTON, timeout=2.0):
            self.click(*self.CART_BUTTON)
        else:
            self.click(*self.CART_BUTTON_FALLBACK)

    def get_cart_badge_count(self) -> int:
        """Return the integer count displayed in cart badge; 0 if not present."""
        if not self.is_displayed(*self.CART_BADGE, timeout=2.0):
            return 0
        raw = self.get_text(*self.CART_BADGE)
        return int(raw) if raw.isdigit() else 0

    def navigate_to_login(self) -> None:
        """Open drawer and select the Login menu option."""
        self.open_menu()
        self.click(*self.LOGIN_MENU_ITEM)

    def is_logged_in(self) -> bool:
        """Check whether Logout option appears in the navigation drawer."""
        self.open_menu()
        displayed = self.is_displayed(*self.LOGOUT_MENU_ITEM, timeout=3.0)
        # Close drawer if open by tapping outside or menu button
        if self.is_displayed(*self.MENU_BUTTON_FALLBACK, timeout=1.0):
            try:
                self.driver.back()
            except Exception:
                pass
        return displayed
