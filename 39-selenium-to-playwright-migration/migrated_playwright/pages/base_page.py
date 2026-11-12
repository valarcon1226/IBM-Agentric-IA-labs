"""Base Page Object for Playwright suite using built-in auto-waiting locators."""

from __future__ import annotations

from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def navigate(self, path: str) -> None:
        url = f"{self.base_url}/{path.lstrip('/')}"
        self.page.goto(url)
        self.dismiss_banners_if_present()

    def dismiss_banners_if_present(self) -> None:
        """Dismiss overlay dialogs or cookie banners if still rendered."""
        for selector in [
            "button[aria-label='Close Welcome Banner']",
            "a[aria-label='dismiss cookie message']",
        ]:
            locator = self.page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                try:
                    locator.first.click(timeout=1000)
                except Exception:
                    pass

    def get_account_button_text(self) -> str:
        account_btn = self.page.locator("#navbarAccount")
        account_btn.wait_for(state="visible")
        return account_btn.inner_text().strip()
