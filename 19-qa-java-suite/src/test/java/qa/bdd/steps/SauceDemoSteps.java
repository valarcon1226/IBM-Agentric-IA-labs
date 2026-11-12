package qa.bdd.steps;

import io.cucumber.java.After;
import io.cucumber.java.Before;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.edge.EdgeOptions;
import org.openqa.selenium.remote.RemoteWebDriver;
import java.net.URL;

import qa.ui.pages.LoginPage;
import qa.ui.pages.InventoryPage;
import qa.ui.pages.CartPage;
import qa.ui.pages.CheckoutPage;

import static org.junit.jupiter.api.Assertions.*;

public class SauceDemoSteps {
    private WebDriver driver;
    private InventoryPage inventoryPage;

    @Before
    public void setup() throws Exception {
        String seleniumUrl = System.getenv("SELENIUM_URL");
        if(seleniumUrl == null) {
            seleniumUrl = "http://localhost:4444/wd/hub";
        }
        EdgeOptions options = new EdgeOptions();
        driver = new RemoteWebDriver(new URL(seleniumUrl), options);
        driver.get("https://www.saucedemo.com/");
    }

    @After
    public void teardown() {
        if(driver != null) {
            driver.quit();
        }
    }

    @Given("I am logged in as {string} with password {string}")
    public void i_am_logged_in_as_with_password(String username, String password) {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login(username, password);
        inventoryPage = new InventoryPage(driver);
    }

    @When("I add the backpack to the cart")
    public void i_add_the_backpack_to_the_cart() {
        inventoryPage.addBackpackToCart();
    }

    @Then("the cart badge should show {string}")
    public void the_cart_badge_should_show(String expectedCount) {
        assertEquals(expectedCount, inventoryPage.getCartCount());
    }

    @When("I add all six products to the cart")
    public void iAddAllSixProductsToTheCart() {
        inventoryPage.addAllProductsToCart();
    }

    @When("I remove the backpack from the inventory page")
    public void iRemoveTheBackpackFromTheInventoryPage() {
        inventoryPage.removeBackpackFromInventory();
    }

    @Then("the cart badge should not show {string}")
    public void theCartBadgeShouldNotShow(String count) {
        assertNotEquals(count, inventoryPage.getCartCount());
    }

    @When("I go to checkout and fill form with {string}, {string}, {string}")
    public void i_go_to_checkout_and_fill_form(String fName, String lName, String zip) {
        inventoryPage.goToCart();
        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();
        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm(fName, lName, zip);
        checkoutPage.clickContinue();
    }

    @Then("I should see the error {string}")
    public void i_should_see_the_error(String errorText) {
        CheckoutPage checkoutPage = new CheckoutPage(driver);
        String actualError = "";
        try {
            actualError = checkoutPage.getErrorMessage();
        } catch(Exception e) {}
        assertTrue(actualError.contains(errorText), "Expected error missing. Got: " + actualError);
    }

    @When("I go to the cart and remove the backpack")
    public void i_go_to_the_cart_and_remove_the_backpack() {
        inventoryPage.goToCart();
        CartPage cartPage = new CartPage(driver);
        cartPage.removeBackpack();
        // go back to inventory to check badge
        driver.navigate().back(); 
    }

    @When("I add the bike light to the cart")
    public void i_add_the_bike_light_to_the_cart() {
        inventoryPage.addBikeLightToCart();
    }

    @When("I complete the checkout with {string}, {string}, {string}")
    public void i_complete_the_checkout_with(String fName, String lName, String zip) {
        inventoryPage.goToCart();
        CartPage cartPage = new CartPage(driver);
        cartPage.goToCheckout();
        CheckoutPage checkoutPage = new CheckoutPage(driver);
        checkoutPage.fillForm(fName, lName, zip);
        checkoutPage.clickContinue();
        checkoutPage.clickFinish();
    }

    @Then("I should see the complete order confirmation {string}")
    public void i_should_see_the_complete_order_confirmation(String expectedText) {
        CheckoutPage checkoutPage = new CheckoutPage(driver);
        assertEquals(expectedText, checkoutPage.getCompleteHeader());
    }

    @Then("I should see the exact error {string}")
    public void i_should_see_the_exact_error(String errorText) {
        CheckoutPage checkoutPage = new CheckoutPage(driver);
        assertEquals(errorText, checkoutPage.getErrorMessage());
    }
}
