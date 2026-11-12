"""Base Page Object for Selenium 4 suite using explicit WebDriverWait."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BasePage:
    def __init__(self, driver: WebDriver, base_url: str, timeout: int = 10) -> None:
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, timeout)

    def navigate(self, path: str) -> None:
        url = f"{self.base_url}/{path.lstrip('/')}"
        self.driver.get(url)
        self.dismiss_banners_if_present()

    def dismiss_banners_if_present(self) -> None:
        """Dismiss overlay dialogs or cookie banners if still rendered."""
        for selector in [
            "button[aria-label='Close Welcome Banner']",
            "a[aria-label='dismiss cookie message']",
        ]:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                try:
                    self.driver.execute_script("arguments[0].click();", elements[0])
                except Exception:
                    pass

    def get_account_button_text(self) -> str:
        account_btn = self.wait.until(
            EC.visibility_of_element_located((By.ID, "navbarAccount"))
        )
        return account_btn.text.strip()
