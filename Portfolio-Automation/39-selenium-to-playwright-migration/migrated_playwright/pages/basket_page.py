"""Shopping Basket Page Object for Playwright suite."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class BasketPage(BasePage):
    BASKET_NAV_BUTTON = "button[routerlink='/basket']"
    BASKET_TABLE = "mat-table"
    BASKET_ROWS = "mat-row"
    REMOVE_BUTTON = "mat-cell.cdk-column-remove button, mat-cell.mat-column-remove button"
    CHECKOUT_BUTTON = "#checkoutButton"

    def open(self) -> BasketPage:
        nav_btn = self.page.locator(self.BASKET_NAV_BUTTON)
        if nav_btn.count() > 0 and nav_btn.first.is_visible():
            nav_btn.first.click()
        else:
            self.navigate("#/basket")
        self.page.wait_for_url("**/#/basket")
        self.page.locator(self.BASKET_TABLE).wait_for(state="visible")
        return self

    def get_item_count(self) -> int:
        self.page.locator(self.BASKET_TABLE).wait_for(state="visible")
        try:
            self.page.locator(self.BASKET_ROWS).first.wait_for(state="visible", timeout=3000)
        except Exception:
            pass
        return self.page.locator(self.BASKET_ROWS).count()

    def remove_first_item(self) -> None:
        row_count_before = self.get_item_count()
        remove_btn = self.page.locator(self.REMOVE_BUTTON).first
        remove_btn.click()

        if row_count_before == 1:
            self.page.wait_for_function("document.querySelectorAll('mat-row').length === 0")
        else:
            self.page.wait_for_function(
                f"document.querySelectorAll('mat-row').length < {row_count_before}"
            )

    def is_empty(self) -> bool:
        return self.page.locator(self.BASKET_ROWS).count() == 0
