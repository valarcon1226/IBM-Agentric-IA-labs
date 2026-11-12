import pytest

from tests.data import USERS
from tests.pages.inventory_page import InventoryPage
from tests.pages.login_page import LoginPage


@pytest.mark.parametrize("user_type", ["standard", "problem"])
def test_valid_login(page, user_type):
    login_page = LoginPage(page)
    inventory_page = InventoryPage(page)
    login_page.navigate()
    login_page.login(USERS[user_type]["username"], USERS[user_type]["password"])
    assert inventory_page.title.inner_text() == "Products"


def test_locked_out_user(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["locked_out"]["username"], USERS["locked_out"]["password"])
    assert (
        "Epic sadface: Sorry, this user has been locked out."
        in login_page.error_message.inner_text()
    )


def test_invalid_login_wrong_password(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["standard"]["username"], "wrong_password")
    assert (
        "Epic sadface: Username and password do not match any user in this service"
        in login_page.error_message.inner_text()
    )


def test_invalid_login_empty_fields(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login("", "")
    assert "Epic sadface: Username is required" in login_page.error_message.inner_text()
