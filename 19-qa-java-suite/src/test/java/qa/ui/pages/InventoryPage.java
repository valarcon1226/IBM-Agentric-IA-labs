package qa.ui.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;

import org.openqa.selenium.support.ui.ExpectedConditions;

public class InventoryPage extends BasePage {
    private By sortDropdown = By.className("product_sort_container");
    private By inventoryItemImg = By.className("inventory_item_img");
    private By addToCartBackpackBtn = By.id("add-to-cart-sauce-labs-backpack");
    private By addToCartBikeLightBtn = By.id("add-to-cart-sauce-labs-bike-light");
    private By removeBackpackBtn = By.id("remove-sauce-labs-backpack");
    private static final String[] ALL_PRODUCTS = {
        "sauce-labs-backpack", "sauce-labs-bike-light", "sauce-labs-bolt-t-shirt",
        "sauce-labs-fleece-jacket", "sauce-labs-onesie", "test.allthethings()-t-shirt-(red)"
    };
    private By cartBadge = By.className("shopping_cart_badge");
    private By cartLink = By.className("shopping_cart_link");

    public InventoryPage(WebDriver driver) {
        super(driver);
    }

    public void selectSort(String value) {
        wait.until(ExpectedConditions.visibilityOfElementLocated(sortDropdown)).sendKeys(value);
    }

    public String getFirstItemImageSrc() {
        return wait.until(ExpectedConditions.visibilityOfElementLocated(inventoryItemImg)).findElement(By.tagName("img")).getAttribute("src");
    }

    public void addBackpackToCart() {
        wait.until(ExpectedConditions.elementToBeClickable(addToCartBackpackBtn)).click();
    }

    public void addBikeLightToCart() {
        wait.until(ExpectedConditions.elementToBeClickable(addToCartBikeLightBtn)).click();
    }

    public void addAllProductsToCart() {
        for (String product : ALL_PRODUCTS) {
            wait.until(ExpectedConditions.elementToBeClickable(By.id("add-to-cart-" + product))).click();
        }
    }

    public void removeBackpackFromInventory() {
        wait.until(ExpectedConditions.elementToBeClickable(removeBackpackBtn)).click();
    }

    public String getCartCount() {
        try {
            return driver.findElement(cartBadge).getText();
        } catch(Exception e) {
            return "0";
        }
    }

    public void goToCart() {
        wait.until(ExpectedConditions.elementToBeClickable(cartLink)).click();
    }
}
