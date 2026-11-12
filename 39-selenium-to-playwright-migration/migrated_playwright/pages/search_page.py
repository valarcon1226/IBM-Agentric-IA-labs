"""Catalog and Search Page Object for Playwright suite."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class SearchPage(BasePage):
    SEARCH_CONTAINER = "#searchQuery"
    SEARCH_INPUT = "#searchQuery input"
    PRODUCT_CARDS = "mat-card"
    EMPTY_STATE = ".emptyState, mat-card.emptyState"
    ADD_TO_BASKET_BUTTON = "button[aria-label='Add to Basket']"
    SNACKBAR = "snack-bar-container"
    LANGUAGE_BUTTON = "button[aria-label='Language selection menu']"

    def open(self) -> SearchPage:
        self.navigate("#/search")
        self.page.locator(self.SEARCH_CONTAINER).wait_for(state="visible")
        self.page.locator(self.PRODUCT_CARDS).first.wait_for(state="visible")
        return self

    def search(self, query: str) -> None:
        self.page.locator(self.SEARCH_CONTAINER).click()
        search_input = self.page.locator(self.SEARCH_INPUT)
        search_input.fill(query)
        search_input.press("Enter")

    def get_product_card_count(self) -> int:
        self.page.locator(self.PRODUCT_CARDS).first.wait_for(state="visible")
        return self.page.locator(self.PRODUCT_CARDS).count()

    def get_first_product_title(self) -> str:
        self.page.locator(self.PRODUCT_CARDS).first.wait_for(state="visible")
        return self.page.locator(self.PRODUCT_CARDS).first.inner_text()

    def get_empty_state_text(self) -> str:
        empty_el = self.page.locator(self.EMPTY_STATE).first
        empty_el.wait_for(state="visible")
        return empty_el.inner_text().strip()

    def add_first_product_to_cart(self) -> None:
        add_btn = self.page.locator(self.ADD_TO_BASKET_BUTTON).first
        add_btn.scroll_into_view_if_needed()
        add_btn.click()
        self.page.locator(self.SNACKBAR).first.wait_for(state="visible")

    def change_language(self, language_label: str = "Deutsch") -> None:
        self.page.locator(self.LANGUAGE_BUTTON).click()
        option = self.page.locator(
            f".mat-menu-panel mat-radio-button:has-text('{language_label}'), "
            f".mat-menu-panel .mat-menu-item:has-text('{language_label}')"
        ).first
        option.click()

        expected_token = "Konto" if language_label == "Deutsch" else language_label
        self.page.locator(f"#navbarAccount:has-text('{expected_token}')").wait_for(state="visible")
