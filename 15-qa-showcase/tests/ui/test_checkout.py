import pytest

from tests.data import PRODUCTS, USERS
from tests.pages.cart_page import CartPage
from tests.pages.checkout_page import CheckoutPage
from tests.pages.inventory_page import InventoryPage
from tests.pages.login_page import LoginPage


@pytest.mark.parametrize(
    "user_type",
    [
        "standard",
        pytest.param("problem", marks=pytest.mark.xfail(strict=True, reason="QA-105")),
    ],
)
def test_successful_checkout(page, user_type):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS[user_type]["username"], USERS[user_type]["password"])

    inventory_page = InventoryPage(page)
    inventory_page.add_to_cart(PRODUCTS["backpack"])
    inventory_page.go_to_cart()

    cart_page = CartPage(page)
    cart_page.click_checkout()

    checkout_page = CheckoutPage(page)
    checkout_page.fill_info("John", "Doe", "12345")
    checkout_page.click_continue()

    item_total = float(page.locator(".summary_subtotal_label").inner_text().split("$")[1])
    tax = float(page.locator(".summary_tax_label").inner_text().split("$")[1])
    total = float(page.locator(".summary_total_label").inner_text().split("$")[1])
    assert item_total + tax == pytest.approx(total, abs=0.01)

    checkout_page.click_finish()
    assert "Thank you for your order!" in checkout_page.complete_header.inner_text()


def test_checkout_form_validations(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["standard"]["username"], USERS["standard"]["password"])

    inventory_page = InventoryPage(page)
    inventory_page.add_to_cart(PRODUCTS["backpack"])
    inventory_page.go_to_cart()

    cart_page = CartPage(page)
    cart_page.click_checkout()

    checkout_page = CheckoutPage(page)

    checkout_page.fill_info("", "Doe", "12345")
    checkout_page.click_continue()
    assert "Error: First Name is required" in page.locator("[data-test='error']").inner_text()

    checkout_page.fill_info("John", "", "12345")
    checkout_page.click_continue()
    assert "Error: Last Name is required" in page.locator("[data-test='error']").inner_text()

    checkout_page.fill_info("John", "Doe", "")
    checkout_page.click_continue()
    assert "Error: Postal Code is required" in page.locator("[data-test='error']").inner_text()
