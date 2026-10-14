package qa.ui.tests;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import qa.ui.pages.CartPage;
import qa.ui.pages.CheckoutPage;
import qa.ui.pages.InventoryPage;
import qa.ui.pages.LoginPage;

import static org.junit.jupiter.api.Assertions.*;

public class CartCheckoutTest extends BaseTest {

    @Test
    @DisplayName("CP-01: Carrito con 2 productos")
    public void testCartWithTwoProducts() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.addBikeLightToCart();
        assertEquals("2", inventoryPage.getCartCount(), "El badge del carrito debe mostrar 2 items");

        inventoryPage.goToCart();
        CartPage cartPage = new CartPage(driver);
        assertEquals(2, cartPage.getItemCount(), "La página del carrito debe listar 2 items");
    }

    @Test
    @DisplayName("CP-02: Checkout completo hasta 'Thank you for your order!'")
    public void testCompleteCheckoutJourney() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.addBikeLightToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("Jane", "Doe", "90210");
        checkoutPage.clickContinue();

        assertTrue(driver.getCurrentUrl().contains("checkout-step-two.html"), "Debe estar en checkout-step-two");

        checkoutPage.clickFinish();
        assertTrue(driver.getCurrentUrl().contains("checkout-complete.html"), "Debe estar en checkout-complete");
        assertEquals("Thank you for your order!", checkoutPage.getCompleteHeader(), "Mensaje de confirmación final");
    }

    @Test
    @DisplayName("CP-03: Validación de nombre vacío en formulario de checkout")
    public void testCheckoutEmptyFirstNameValidation() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("", "Doe", "90210");
        checkoutPage.clickContinue();

        assertEquals("Error: First Name is required", checkoutPage.getErrorMessage());
    }

    @Test
    @DisplayName("CP-04: Validación de apellido vacío en formulario de checkout")
    public void testCheckoutEmptyLastNameValidation() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("Jane", "", "90210");
        checkoutPage.clickContinue();

        assertEquals("Error: Last Name is required", checkoutPage.getErrorMessage());
    }

    @Test
    @DisplayName("CP-05: Validación de código postal vacío en formulario de checkout")
    public void testCheckoutEmptyPostalCodeValidation() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("Jane", "Doe", "");
        checkoutPage.clickContinue();

        assertEquals("Error: Postal Code is required", checkoutPage.getErrorMessage());
    }

    @Test
    @DisplayName("CP-06: Verificación de Total = Subtotal + Impuesto (tolerancia 0.01)")
    public void testTotalEqualsSubtotalPlusTax() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.addBikeLightToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("Jane", "Doe", "90210");
        checkoutPage.clickContinue();

        double subtotal = checkoutPage.getSubtotal();
        double tax = checkoutPage.getTax();
        double total = checkoutPage.getTotal();

        assertTrue(subtotal > 0, "Subtotal debe ser mayor a 0");
        assertTrue(tax > 0, "Impuesto debe ser mayor a 0");
        assertEquals(subtotal + tax, total, 0.01, "El total debe ser igual a subtotal + tax con tolerancia 0.01");
    }

    @Test
    @DisplayName("CP-07: Cancelar checkout en paso 1 retorna al carrito")
    public void testCancelCheckoutStepOne() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.clickCancel();

        assertTrue(driver.getCurrentUrl().contains("cart.html"), "Cancelar debe retornar a la página de carrito");
    }

    @Test
    @DisplayName("CP-08: Cancelar checkout en paso 2 retorna al inventario")
    public void testCancelCheckoutStepTwo() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");

        InventoryPage inventoryPage = new InventoryPage(driver);
        inventoryPage.addBackpackToCart();
        inventoryPage.goToCart();

        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();

        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm("Jane", "Doe", "90210");
        checkoutPage.clickContinue();

        checkoutPage.clickCancel();
        assertTrue(driver.getCurrentUrl().contains("inventory.html"), "Cancelar en paso 2 debe retornar al inventario");
    }
}
