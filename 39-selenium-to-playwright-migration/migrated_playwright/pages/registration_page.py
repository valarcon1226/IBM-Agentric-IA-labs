"""Registration Page Object for Playwright suite."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class RegistrationPage(BasePage):
    EMAIL_INPUT = "#emailControl"
    PASSWORD_INPUT = "#passwordControl"
    REPEAT_PASSWORD_INPUT = "#repeatPasswordControl"
    SECURITY_QUESTION_SELECT = "mat-select[name='securityQuestion']"
    SECURITY_QUESTION_OPTION = "mat-option"
    SECURITY_ANSWER_INPUT = "#securityAnswerControl"
    REGISTER_BUTTON = "#registerButton"

    def open(self) -> RegistrationPage:
        self.navigate("#/register")
        self.page.locator(self.EMAIL_INPUT).wait_for(state="visible")
        return self

    def register(
        self,
        email: str,
        password: str,
        security_answer: str = "TestSecurityAnswer",
    ) -> None:
        self.page.locator(self.EMAIL_INPUT).fill(email)
        self.page.locator(self.PASSWORD_INPUT).fill(password)
        self.page.locator(self.REPEAT_PASSWORD_INPUT).fill(password)

        # Open security question dropdown
        self.page.locator(self.SECURITY_QUESTION_SELECT).click()
        self.page.locator(self.SECURITY_QUESTION_OPTION).first.click()

        self.page.locator(self.SECURITY_ANSWER_INPUT).fill(security_answer)
        self.page.locator(self.REGISTER_BUTTON).click()

    def is_registration_successful(self) -> bool:
        self.page.wait_for_url("**/#/login")
        return "/#/login" in self.page.url
