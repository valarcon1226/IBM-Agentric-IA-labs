"""Shopping Basket Page Object for Selenium 4 suite."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base_page import BasePage


class BasketPage(BasePage):
    BASKET_NAV_BUTTON = (By.CSS_SELECTOR, "button[routerlink='/basket']")
    BASKET_TABLE = (By.TAG_NAME, "mat-table")
    BASKET_ROWS = (By.TAG_NAME, "mat-row")
    REMOVE_BUTTON = (
        By.CSS_SELECTOR,
        "mat-cell.cdk-column-remove button, mat-cell.mat-column-remove button",
    )
    CHECKOUT_BUTTON = (By.ID, "checkoutButton")

    def open(self) -> BasketPage:
        nav_buttons = self.driver.find_elements(*self.BASKET_NAV_BUTTON)
        if nav_buttons and nav_buttons[0].is_displayed():
            nav_buttons[0].click()
        else:
            self.navigate("#/basket")
        self.wait.until(EC.url_contains("/#/basket"))
        self.wait.until(EC.presence_of_element_located(self.BASKET_TABLE))
        return self

    def get_item_count(self) -> int:
        self.wait.until(EC.presence_of_element_located(self.BASKET_TABLE))
        try:
            self.wait.until(EC.presence_of_element_located(self.BASKET_ROWS))
        except Exception:
            pass
        return len(self.driver.find_elements(*self.BASKET_ROWS))

    def remove_first_item(self) -> None:
        row_count_before = self.get_item_count()
        remove_btn = self.wait.until(EC.element_to_be_clickable(self.REMOVE_BUTTON))
        remove_btn.click()

        if row_count_before == 1:
            self.wait.until(EC.invisibility_of_element_located(self.BASKET_ROWS))
        else:
            self.wait.until(
                lambda d: len(d.find_elements(*self.BASKET_ROWS)) < row_count_before
            )

    def is_empty(self) -> bool:
        rows = self.driver.find_elements(*self.BASKET_ROWS)
        return len(rows) == 0
