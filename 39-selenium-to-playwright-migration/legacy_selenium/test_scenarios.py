"""Legacy Selenium 4 test scenarios matching Cypress e2e specifications."""

from __future__ import annotations

import time
import uuid

from .helpers.api_client import create_user
from .pages.basket_page import BasketPage
from .pages.login_page import LoginPage
from .pages.registration_page import RegistrationPage
from .pages.search_page import SearchPage


def test_login_valid(driver, base_url: str) -> None:
    """SC-AUTH-03: Successfully login via UI with valid credentials."""
    user = create_user(base_url)
    login_page = LoginPage(driver, base_url).open()
    login_page.login(user["email"], user["password"])
    assert login_page.is_logged_in(), "Expected user to be logged in and redirected to search"


def test_login_invalid(driver, base_url: str) -> None:
    """SC-AUTH-04: Reject login with invalid credentials and display error."""
    login_page = LoginPage(driver, base_url).open()
    login_page.login("nonexistent-user@juice-sh.op", "WrongPassword123!", wait_for_success=False)
    error_msg = login_page.get_error_message()
    assert "Invalid email or password" in error_msg


def test_user_registration(driver, base_url: str) -> None:
    """SC-AUTH-01: Successfully register a new disposable user via UI."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"selenium-reg-{unique_id}-{int(time.time())}@juice-sh.op"
    password = "JuicePassword123!"

    reg_page = RegistrationPage(driver, base_url).open()
    reg_page.register(email, password, security_answer="SeleniumColor")
    assert reg_page.is_registration_successful(), "Expected redirection to login after registration"


def test_search_with_results(driver, base_url: str) -> None:
    """SC-CAT-01: Search for an existing product and verify matching cards."""
    search_page = SearchPage(driver, base_url).open()
    search_page.search("apple")
    assert search_page.get_product_card_count() >= 1
    assert "apple" in search_page.get_first_product_title().lower()


def test_search_without_results(driver, base_url: str) -> None:
    """SC-CAT-02: Search for non-existent product shows empty results."""
    search_page = SearchPage(driver, base_url).open()
    search_page.search("xyznonexistentproduct999")
    empty_text = search_page.get_empty_state_text().lower()
    assert "no results found" in empty_text


def test_add_to_cart(driver, base_url: str) -> None:
    """SC-CART-01: Add product to basket and verify item is present in basket."""
    user = create_user(base_url)
    LoginPage(driver, base_url).open().login(user["email"], user["password"])

    search_page = SearchPage(driver, base_url).open()
    search_page.add_first_product_to_cart()

    basket_page = BasketPage(driver, base_url).open()
    assert basket_page.get_item_count() >= 1


def test_remove_from_cart(driver, base_url: str) -> None:
    """SC-CART-02: Add item to basket, delete it, and verify basket is empty."""
    user = create_user(base_url)
    LoginPage(driver, base_url).open().login(user["email"], user["password"])

    search_page = SearchPage(driver, base_url).open()
    search_page.add_first_product_to_cart()

    basket_page = BasketPage(driver, base_url).open()
    assert basket_page.get_item_count() >= 1

    basket_page.remove_first_item()
    assert basket_page.is_empty(), "Expected shopping basket to be empty after item removal"


def test_language_change(driver, base_url: str) -> None:
    """SC-LANG-01: Change UI language to German and verify localized text."""
    search_page = SearchPage(driver, base_url).open()
    search_page.change_language("Deutsch")
    account_text = search_page.get_account_button_text().lower()
    assert "konto" in account_text
