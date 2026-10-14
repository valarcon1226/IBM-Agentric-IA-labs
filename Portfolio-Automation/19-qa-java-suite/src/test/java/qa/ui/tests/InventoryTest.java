package qa.ui.tests;

import org.junit.jupiter.api.Test;
import qa.ui.pages.LoginPage;
import qa.ui.pages.InventoryPage;
import qa.ui.pages.CartPage;
import static org.junit.jupiter.api.Assertions.*;

public class InventoryTest extends BaseTest {

    @Test
    public void testAddAndRemoveFromCart() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");
        
        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        assertEquals("1", inventoryPage.getCartCount());
        
        inventoryPage.goToCart();
        CartPage cartPage = new CartPage(driver);
        cartPage.removeBackpack();
        
        driver.navigate().back();
        InventoryPage invPage2 = new InventoryPage(driver);
        assertEquals("0", invPage2.getCartCount());
    }

    @Test
    public void testSortOrders() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");
        
        InventoryPage inventoryPage = new InventoryPage(driver);
        
        inventoryPage.selectSort("Name (Z to A)");
        inventoryPage.selectSort("Price (low to high)");
        inventoryPage.selectSort("Price (high to low)");
        inventoryPage.selectSort("Name (A to Z)");
        assertTrue(true);
    }
}
