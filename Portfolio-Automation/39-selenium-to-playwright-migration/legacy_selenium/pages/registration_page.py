"""Registration Page Object for Selenium 4 suite."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base_page import BasePage


class RegistrationPage(BasePage):
    EMAIL_INPUT = (By.ID, "emailControl")
    PASSWORD_INPUT = (By.ID, "passwordControl")
    REPEAT_PASSWORD_INPUT = (By.ID, "repeatPasswordControl")
    SECURITY_QUESTION_SELECT = (By.CSS_SELECTOR, "mat-select[name='securityQuestion']")
    SECURITY_QUESTION_OPTION = (By.CSS_SELECTOR, "mat-option")
    SECURITY_ANSWER_INPUT = (By.ID, "securityAnswerControl")
    REGISTER_BUTTON = (By.ID, "registerButton")

    def open(self) -> RegistrationPage:
        self.navigate("#/register")
        self.wait.until(EC.visibility_of_element_located(self.EMAIL_INPUT))
        return self

    def register(
        self,
        email: str,
        password: str,
        security_answer: str = "TestSecurityAnswer",
    ) -> None:
        email_el = self.wait.until(EC.element_to_be_clickable(self.EMAIL_INPUT))
        email_el.send_keys(email)

        pwd_el = self.wait.until(EC.element_to_be_clickable(self.PASSWORD_INPUT))
        pwd_el.send_keys(password)

        rep_pwd_el = self.wait.until(EC.element_to_be_clickable(self.REPEAT_PASSWORD_INPUT))
        rep_pwd_el.send_keys(password)

        # Open security question dropdown
        select_el = self.wait.until(EC.presence_of_element_located(self.SECURITY_QUESTION_SELECT))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_el)
        self.driver.execute_script("arguments[0].click();", select_el)

        option_el = self.wait.until(EC.element_to_be_clickable(self.SECURITY_QUESTION_OPTION))
        option_el.click()

        # Synchronize: wait until the Angular overlay backdrop and panels are dismissed
        def no_overlay_blocking(d):
            panes = d.find_elements(By.CSS_SELECTOR, ".cdk-overlay-pane")
            return all(not p.is_displayed() for p in panes)

        self.wait.until(no_overlay_blocking)

        ans_el = self.wait.until(EC.element_to_be_clickable(self.SECURITY_ANSWER_INPUT))
        ans_el.send_keys(security_answer)

        reg_btn = self.wait.until(EC.presence_of_element_located(self.REGISTER_BUTTON))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reg_btn)
        self.wait.until(EC.element_to_be_clickable(self.REGISTER_BUTTON)).click()

    def is_registration_successful(self) -> bool:
        return self.wait.until(EC.url_contains("/#/login"))
