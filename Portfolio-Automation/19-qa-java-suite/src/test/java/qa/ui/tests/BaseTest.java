package qa.ui.tests;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.edge.EdgeOptions;
import org.openqa.selenium.remote.RemoteWebDriver;
import java.net.URL;

public class BaseTest {
    protected WebDriver driver;

    @BeforeEach
    public void setup() throws Exception {
        String seleniumUrl = System.getenv("SELENIUM_URL");
        if(seleniumUrl == null) {
            seleniumUrl = "http://localhost:4444/wd/hub";
        }
        EdgeOptions options = new EdgeOptions();
        driver = new RemoteWebDriver(new URL(seleniumUrl), options);
        driver.get("https://www.saucedemo.com/");
    }

    @AfterEach
    public void teardown() {
        if(driver != null) {
            driver.quit();
        }
    }
}
