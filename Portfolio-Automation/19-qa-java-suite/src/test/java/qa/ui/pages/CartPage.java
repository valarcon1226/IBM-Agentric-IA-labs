package qa.ui.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

import org.openqa.selenium.support.ui.ExpectedConditions;

public class CartPage extends BasePage {
    private By removeBackpackBtn = By.id("remove-sauce-labs-backpack");
    private By checkoutBtn = By.id("checkout");

    private By cartItems = By.className("cart_item");
    private By continueShoppingBtn = By.id("continue-shopping");

    public CartPage(WebDriver driver) {
        super(driver);
    }

    public void removeBackpack() {
        wait.until(ExpectedConditions.elementToBeClickable(removeBackpackBtn)).click();
    }

    public void goToCheckout() {
        wait.until(ExpectedConditions.elementToBeClickable(checkoutBtn)).click();
    }

    public int getItemCount() {
        return driver.findElements(cartItems).size();
    }

    public void continueShopping() {
        wait.until(ExpectedConditions.elementToBeClickable(continueShoppingBtn)).click();
    }
}
