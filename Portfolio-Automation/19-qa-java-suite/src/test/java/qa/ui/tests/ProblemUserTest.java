package qa.ui.tests;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Tag;
import qa.ui.pages.LoginPage;
import qa.ui.pages.InventoryPage;
import qa.ui.pages.CartPage;
import qa.ui.pages.CheckoutPage;
import static org.junit.jupiter.api.Assertions.*;

public class ProblemUserTest extends BaseTest {

    @Test
    @Tag("known-bug")
    public void testAddToCart_QA104() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("problem_user", "secret_sauce");
        
        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addAllProductsToCart();

        // Bug QA-104 (sigue presente): con problem_user algunos "Add to cart" no hacen nada,
        // asi que tras pulsar los 6 productos el carrito no llega a 6.
        assertNotEquals("6", inventoryPage.getCartCount(), "QA-104 ya no se reproduce: revisar si fue corregido");
    }
    
    @Test
    @Tag("known-bug")
    public void testCheckoutLastName_QA105() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("problem_user", "secret_sauce");
        
        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.goToCart();
        
        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();
        
        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("John", "Doe", "12345");
        checkoutPage.clickContinue();
        
        // Bug QA-105: El apellido no queda escrito en el checkout
        String errorMsg = checkoutPage.getErrorMessage();
        assertTrue(errorMsg.contains("Last Name is required"), "QA-105: Last Name is required error is present");
    }
    
    @Test
    @Tag("known-bug")
    public void testRemoveFromCart_QA106() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("problem_user", "secret_sauce");
        
        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.removeBackpackFromInventory();

        // Bug QA-106 (sigue presente): con problem_user el boton Remove del inventario no quita el producto.
        assertEquals("1", inventoryPage.getCartCount(), "QA-106 ya no se reproduce: revisar si fue corregido");
    }
}
