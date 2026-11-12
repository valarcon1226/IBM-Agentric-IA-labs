"""Screen Object for the Login authentication screen."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from screens.base_screen import BaseScreen


class LoginScreen(BaseScreen):
    """Authentication view with credentials entry, demo shortcuts, and validation errors."""

    LOGIN_TITLE = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/loginTV")
    USERNAME_INPUT = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/nameET")
    PASSWORD_INPUT = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/passwordET")

    LOGIN_BUTTON = (AppiumBy.ACCESSIBILITY_ID, "Tap to login with given credentials")
    LOGIN_BUTTON_FALLBACK = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/loginBtn")

    # Error message displays
    PASSWORD_ERROR_TEXT = (
        AppiumBy.ID,
        "com.saucelabs.mydemoapp.android:id/passwordErrorTV",
    )
    USERNAME_ERROR_TEXT = (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/nameErrorTV")

    # Demo quick-fill options
    DEMO_USER_STANDARD = (
        AppiumBy.ID,
        "com.saucelabs.mydemoapp.android:id/username1TV",
    )
    DEMO_USER_LOCKED_OUT = (
        AppiumBy.ID,
        "com.saucelabs.mydemoapp.android:id/username2TV",
    )

    def is_loaded(self) -> bool:
        """Verify login screen title and input fields are visible."""
        return (
            self.is_displayed(*self.LOGIN_TITLE, timeout=8.0)
            and self.is_displayed(*self.USERNAME_INPUT, timeout=8.0)
            and self.is_displayed(*self.PASSWORD_INPUT, timeout=8.0)
        )

    def enter_username(self, username: str) -> None:
        """Input username."""
        self.send_keys(*self.USERNAME_INPUT, text=username, clear=True)

    def enter_password(self, password: str) -> None:
        """Input password."""
        self.send_keys(*self.PASSWORD_INPUT, text=password, clear=True)

    def submit_login(self) -> None:
        """Click the login submit button."""
        if self.is_displayed(*self.LOGIN_BUTTON, timeout=2.0):
            self.click(*self.LOGIN_BUTTON)
        else:
            self.click(*self.LOGIN_BUTTON_FALLBACK)

    def login(self, username: str, password: str) -> None:
        """Complete login with the given credentials."""
        self.enter_username(username)
        self.enter_password(password)
        self.submit_login()

    def autofill_standard_user(self) -> None:
        """Tap demo shortcut for standard user (bod@example.com / 10203040)."""
        self.click(*self.DEMO_USER_STANDARD)

    def autofill_locked_out_user(self) -> None:
        """Tap demo shortcut for locked-out user (alice@example.com / 10203040)."""
        self.click(*self.DEMO_USER_LOCKED_OUT)

    def get_error_message(self) -> str:
        """Retrieve displayed error text."""
        if self.is_displayed(*self.PASSWORD_ERROR_TEXT, timeout=5.0):
            return self.get_text(*self.PASSWORD_ERROR_TEXT)
        if self.is_displayed(*self.USERNAME_ERROR_TEXT, timeout=5.0):
            return self.get_text(*self.USERNAME_ERROR_TEXT)
        return ""
