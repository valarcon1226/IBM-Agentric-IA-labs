import pytest

from tests.data import PRODUCTS, USERS
from tests.pages.cart_page import CartPage
from tests.pages.inventory_page import InventoryPage
from tests.pages.login_page import LoginPage


@pytest.mark.parametrize("user_type", ["standard", "problem"])
def test_cart_contents(page, user_type):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS[user_type]["username"], USERS[user_type]["password"])

    inventory_page = InventoryPage(page)
    inventory_page.add_to_cart(PRODUCTS["backpack"])
    inventory_page.go_to_cart()

    cart_page = CartPage(page)
    items = cart_page.get_item_names()
    assert PRODUCTS["backpack"] in items
