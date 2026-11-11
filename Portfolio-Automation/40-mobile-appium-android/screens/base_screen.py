"""Base Screen object encapsulation using explicit WebDriverWait synchronization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

if TYPE_CHECKING:
    from appium.webdriver.webdriver import WebDriver
    from appium.webdriver.webelement import WebElement


class BaseScreen:
    """Base class for all Android Screen Objects."""

    def __init__(self, driver: WebDriver, timeout: float = 10.0) -> None:
        self.driver = driver
        self.default_timeout = timeout

    def _wait(self, timeout: float | None = None) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout if timeout is not None else self.default_timeout)

    def find(self, by: str, value: str, timeout: float | None = None) -> WebElement:
        """Wait for element to be present and return it."""
        return self._wait(timeout).until(ec.presence_of_element_located((by, value)))

    def find_visible(self, by: str, value: str, timeout: float | None = None) -> WebElement:
        """Wait for element to be visible and return it."""
        return self._wait(timeout).until(ec.visibility_of_element_located((by, value)))

    def find_all(self, by: str, value: str, timeout: float | None = None) -> list[WebElement]:
        """Wait for at least one element to be present and return all matches."""
        try:
            return self._wait(timeout).until(ec.presence_of_all_elements_located((by, value)))
        except TimeoutException:
            return []

    def click(self, by: str, value: str, timeout: float | None = None) -> None:
        """Wait for element to be clickable and click it."""
        element = self._wait(timeout).until(ec.element_to_be_clickable((by, value)))
        element.click()

    def send_keys(
        self,
        by: str,
        value: str,
        text: str,
        clear: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Wait for input element, optionally clear it, and send keys."""
        element = self._wait(timeout).until(ec.visibility_of_element_located((by, value)))
        if clear:
            element.clear()
        element.send_keys(text)

    def get_text(self, by: str, value: str, timeout: float | None = None) -> str:
        """Wait for element and return its text stripped of whitespace."""
        element = self._wait(timeout).until(ec.visibility_of_element_located((by, value)))
        return element.text.strip()

    def is_displayed(self, by: str, value: str, timeout: float = 3.0) -> bool:
        """Check whether element is visible within timeout without throwing."""
        try:
            return bool(
                WebDriverWait(self.driver, timeout).until(
                    ec.visibility_of_element_located((by, value))
                )
            )
        except (TimeoutException, NoSuchElementException):
            return False
