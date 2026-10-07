from .base_page import BasePage


class CartPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.checkout_button = page.locator("[data-test='checkout']")
        self.cart_items = page.locator(".cart_item")

    def get_item_names(self):
        return self.page.locator(".inventory_item_name").all_inner_texts()

    def click_checkout(self):
        self.checkout_button.click()
