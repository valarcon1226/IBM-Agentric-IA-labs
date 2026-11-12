"""Login Page Object for Selenium 4 suite."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base_page import BasePage


class LoginPage(BasePage):
    EMAIL_INPUT = (By.ID, "email")
    PASSWORD_INPUT = (By.ID, "password")
    LOGIN_BUTTON = (By.ID, "loginButton")
    ERROR_CONTAINER = (By.CSS_SELECTOR, ".error, mat-error")

    def open(self) -> LoginPage:
        self.navigate("#/login")
        self.wait.until(EC.visibility_of_element_located(self.EMAIL_INPUT))
        return self

    def login(self, email: str, password: str, wait_for_success: bool = True) -> None:
        email_el = self.wait.until(EC.element_to_be_clickable(self.EMAIL_INPUT))
        email_el.clear()
        email_el.send_keys(email)

        pwd_el = self.wait.until(EC.element_to_be_clickable(self.PASSWORD_INPUT))
        pwd_el.clear()
        pwd_el.send_keys(password)

        login_btn = self.wait.until(EC.element_to_be_clickable(self.LOGIN_BUTTON))
        login_btn.click()

        if wait_for_success:
            self.wait.until(EC.url_contains("/#/search"))
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "mat-card")))

    def get_error_message(self) -> str:
        error_el = self.wait.until(EC.visibility_of_element_located(self.ERROR_CONTAINER))
        return error_el.text.strip()

    def is_logged_in(self) -> bool:
        account_btn = self.wait.until(EC.visibility_of_element_located((By.ID, "navbarAccount")))
        return account_btn.is_displayed()
