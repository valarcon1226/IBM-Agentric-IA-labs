package qa.ui.tests;

import org.junit.jupiter.api.Test;
import qa.ui.pages.LoginPage;
import org.openqa.selenium.By;
import static org.junit.jupiter.api.Assertions.*;

public class LoginTest extends BaseTest {

    @Test
    public void testValidLogin() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "secret_sauce");
        assertTrue(driver.getCurrentUrl().contains("inventory.html"), "Should be on inventory page");
    }

    @Test
    public void testLockedOutUser() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("locked_out_user", "secret_sauce");
        String errorMsg = getLoginError();
        assertEquals("Epic sadface: Sorry, this user has been locked out.", errorMsg);
    }

    @Test
    public void testInvalidPassword() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "wrong_password");
        String errorMsg = getLoginError();
        assertEquals("Epic sadface: Username and password do not match any user in this service", errorMsg);
    }

    @Test
    public void testEmptyFields() {
        LoginPage loginPage = new LoginPage(driver);
        loginPage.login("", "");
        assertEquals("Epic sadface: Username is required", getLoginError());
        
        driver.navigate().refresh();
        loginPage = new LoginPage(driver);
        loginPage.login("standard_user", "");
        assertEquals("Epic sadface: Password is required", getLoginError());
    }

    private String getLoginError() {
        return driver.findElement(By.cssSelector("[data-test='error']")).getText();
    }
}
