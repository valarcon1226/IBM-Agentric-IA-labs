"""Login Page Object for Playwright suite."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class LoginPage(BasePage):
    EMAIL_INPUT = "#email"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "#loginButton"
    ERROR_CONTAINER = ".error, mat-error"

    def open(self) -> LoginPage:
        self.navigate("#/login")
        self.page.locator(self.EMAIL_INPUT).wait_for(state="visible")
        return self

    def login(self, email: str, password: str, wait_for_success: bool = True) -> None:
        self.page.locator(self.EMAIL_INPUT).fill(email)
        self.page.locator(self.PASSWORD_INPUT).fill(password)
        self.page.locator(self.LOGIN_BUTTON).click()

        if wait_for_success:
            self.page.wait_for_url("**/#/search")
            self.page.locator("mat-card").first.wait_for(state="visible")

    def get_error_message(self) -> str:
        error_el = self.page.locator(self.ERROR_CONTAINER).first
        error_el.wait_for(state="visible")
        return error_el.inner_text().strip()

    def is_logged_in(self) -> bool:
        account_btn = self.page.locator("#navbarAccount")
        account_btn.wait_for(state="visible")
        return account_btn.is_visible()
