import pytest

from tests.data import PRODUCTS, USERS
from tests.pages.inventory_page import InventoryPage
from tests.pages.login_page import LoginPage


@pytest.fixture(autouse=True)
def setup(page):
    pass


@pytest.mark.parametrize("user_type", ["standard", "problem"])
def test_add_item_to_cart(page, user_type):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS[user_type]["username"], USERS[user_type]["password"])

    inventory_page = InventoryPage(page)
    inventory_page.add_to_cart(PRODUCTS["backpack"])

    assert inventory_page.cart_badge.inner_text() == "1"


@pytest.mark.parametrize(
    "user_type",
    ["standard", pytest.param("problem", marks=pytest.mark.xfail(strict=True, reason="QA-106"))],
)
def test_remove_item_from_cart(page, user_type):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS[user_type]["username"], USERS[user_type]["password"])

    inventory_page = InventoryPage(page)
    inventory_page.add_to_cart(PRODUCTS["backpack"])
    inventory_page.remove_from_cart(PRODUCTS["backpack"])

    assert inventory_page.cart_badge.is_hidden()


def test_inventory_sorting_standard(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["standard"]["username"], USERS["standard"]["password"])

    page.locator("[data-test='product-sort-container']").select_option("za")
    assert (
        page.locator(".inventory_item_name").nth(0).inner_text()
        == "Test.allTheThings() T-Shirt (Red)"
    )


@pytest.mark.xfail(strict=True, reason="QA-102")
def test_inventory_sorting_problem(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["problem"]["username"], USERS["problem"]["password"])

    page.locator("[data-test='product-sort-container']").select_option("za")
    assert (
        page.locator(".inventory_item_name").nth(0).inner_text()
        == "Test.allTheThings() T-Shirt (Red)"
    )


@pytest.mark.xfail(strict=True, reason="QA-103")
def test_inventory_images_problem(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["problem"]["username"], USERS["problem"]["password"])

    src = page.locator(".inventory_item_img img").nth(0).get_attribute("src")
    assert "sl-404" not in src


@pytest.mark.xfail(strict=True, reason="QA-104")
def test_add_all_items_problem(page):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(USERS["problem"]["username"], USERS["problem"]["password"])

    inventory_page = InventoryPage(page)
    for prod in [
        "backpack",
        "bike-light",
        "bolt-t-shirt",
        "fleece-jacket",
        "onesie",
        "t-shirt-(red)",
    ]:
        page.locator(f"[data-test='add-to-cart-sauce-labs-{prod}']").click()

    assert inventory_page.cart_badge.inner_text() == "6"
