"""Catalog and Search Page Object for Selenium 4 suite."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from .base_page import BasePage


class SearchPage(BasePage):
    SEARCH_CONTAINER = (By.ID, "searchQuery")
    SEARCH_INPUT = (By.CSS_SELECTOR, "#searchQuery input")
    PRODUCT_CARDS = (By.TAG_NAME, "mat-card")
    EMPTY_STATE = (By.CSS_SELECTOR, ".emptyState, mat-card.emptyState")
    ADD_TO_BASKET_BUTTON = (By.CSS_SELECTOR, "button[aria-label='Add to Basket']")
    SNACKBAR = (By.TAG_NAME, "snack-bar-container")
    LANGUAGE_BUTTON = (By.CSS_SELECTOR, "button[aria-label='Language selection menu']")
    LANGUAGE_OPTIONS = (By.CSS_SELECTOR, ".mat-menu-panel mat-radio-button, .mat-menu-panel .mat-menu-item")

    def open(self) -> SearchPage:
        self.navigate("#/search")
        self.wait.until(EC.presence_of_element_located(self.SEARCH_CONTAINER))
        # Wait until products load if catalog is being viewed
        self.wait.until(EC.presence_of_element_located(self.PRODUCT_CARDS))
        return self

    def search(self, query: str) -> None:
        search_btn = self.wait.until(EC.element_to_be_clickable(self.SEARCH_CONTAINER))
        search_btn.click()

        search_input = self.wait.until(EC.visibility_of_element_located(self.SEARCH_INPUT))
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)

    def get_product_card_count(self) -> int:
        self.wait.until(EC.presence_of_element_located(self.PRODUCT_CARDS))
        return len(self.driver.find_elements(*self.PRODUCT_CARDS))

    def get_first_product_title(self) -> str:
        self.wait.until(EC.presence_of_element_located(self.PRODUCT_CARDS))
        first_card = self.driver.find_elements(*self.PRODUCT_CARDS)[0]
        return first_card.text

    def get_empty_state_text(self) -> str:
        empty_el = self.wait.until(EC.visibility_of_element_located(self.EMPTY_STATE))
        return empty_el.text.strip()

    def add_first_product_to_cart(self) -> None:
        add_btn = self.wait.until(EC.element_to_be_clickable(self.ADD_TO_BASKET_BUTTON))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_btn)
        add_btn.click()
        # Wait for snackbar feedback
        self.wait.until(EC.visibility_of_element_located(self.SNACKBAR))

    def change_language(self, language_label: str = "Deutsch") -> None:
        lang_btn = self.wait.until(EC.element_to_be_clickable(self.LANGUAGE_BUTTON))
        lang_btn.click()

        self.wait.until(EC.visibility_of_element_located(self.LANGUAGE_OPTIONS))
        options = self.driver.find_elements(*self.LANGUAGE_OPTIONS)
        target = next((opt for opt in options if language_label in opt.text), None)
        if target is None:
            raise ValueError(f"Language option '{language_label}' not found")
        target.click()

        expected_token = "Konto" if language_label == "Deutsch" else language_label
        self.wait.until(EC.text_to_be_present_in_element((By.ID, "navbarAccount"), expected_token))
