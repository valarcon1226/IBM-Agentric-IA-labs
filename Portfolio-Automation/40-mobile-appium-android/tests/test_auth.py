"""User authentication and authorization tests."""

from __future__ import annotations

import pytest

from screens.catalog_screen import CatalogScreen
from screens.login_screen import LoginScreen
from screens.navigation_header import NavigationHeader


@pytest.mark.auth
def test_valid_login(driver) -> None:
    """Scenario 6: Log in with valid demo credentials and verify session state."""
    catalog = CatalogScreen(driver)
    header = NavigationHeader(driver)
    login = LoginScreen(driver)

    assert catalog.is_loaded(), "App should start on Catalog screen"

    header.navigate_to_login()
    assert login.is_loaded(), "Login screen failed to load"

    # Use standard public demo credentials
    login.login(username="bod@example.com", password="10203040")

    # Successful login redirects back to Catalog screen
    assert catalog.is_loaded(), "User was not redirected to Catalog after successful login"
    assert header.is_logged_in(), "Navigation drawer did not reflect logged-in status"


@pytest.mark.auth
def test_locked_out_user_error(driver) -> None:
    """Scenario 7: Attempt login with locked-out user and assert explicit error message."""
    catalog = CatalogScreen(driver)
    header = NavigationHeader(driver)
    login = LoginScreen(driver)

    assert catalog.is_loaded(), "App should start on Catalog screen"

    header.navigate_to_login()
    assert login.is_loaded(), "Login screen failed to load"

    # Use locked out demo credentials
    login.login(username="alice@example.com", password="10203040")

    error_message = login.get_error_message()
    expected_error = "Sorry this user has been locked out."
    assert expected_error in error_message, (
        f"Expected error message containing '{expected_error}', got '{error_message}'"
    )
