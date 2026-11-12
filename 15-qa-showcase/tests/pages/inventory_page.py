from .base_page import BasePage


class InventoryPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.title = page.locator(".title")
        self.cart_icon = page.locator(".shopping_cart_link")
        self.cart_badge = page.locator(".shopping_cart_badge")

    def add_to_cart(self, item_name):
        test_id = f"add-to-cart-{item_name.lower().replace(' ', '-')}"
        self.page.locator(f"[data-test='{test_id}']").click()

    def remove_from_cart(self, item_name):
        test_id = f"remove-{item_name.lower().replace(' ', '-')}"
        self.page.locator(f"[data-test='{test_id}']").click()

    def go_to_cart(self):
        self.cart_icon.click()
