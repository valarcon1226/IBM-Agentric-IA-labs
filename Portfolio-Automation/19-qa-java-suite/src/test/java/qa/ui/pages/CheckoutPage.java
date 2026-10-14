package qa.ui.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

import org.openqa.selenium.support.ui.ExpectedConditions;

public class CheckoutPage extends BasePage {
    private By firstNameInput = By.id("first-name");
    private By lastNameInput = By.id("last-name");
    private By postalCodeInput = By.id("postal-code");
    private By continueBtn = By.id("continue");
    private By errorMsg = By.cssSelector("[data-test='error']");

    private By finishBtn = By.id("finish");
    private By cancelBtn = By.id("cancel");
    private By subtotalLabel = By.className("summary_subtotal_label");
    private By taxLabel = By.className("summary_tax_label");
    private By totalLabel = By.className("summary_total_label");
    private By completeHeader = By.className("complete-header");

    public CheckoutPage(WebDriver driver) {
        super(driver);
    }

    public void fillForm(String fName, String lName, String pCode) {
        wait.until(ExpectedConditions.visibilityOfElementLocated(firstNameInput)).clear();
        driver.findElement(firstNameInput).sendKeys(fName);
        driver.findElement(lastNameInput).clear();
        driver.findElement(lastNameInput).sendKeys(lName);
        driver.findElement(postalCodeInput).clear();
        driver.findElement(postalCodeInput).sendKeys(pCode);
    }

    public void clickContinue() {
        wait.until(ExpectedConditions.elementToBeClickable(continueBtn)).click();
    }

    public void clickFinish() {
        wait.until(ExpectedConditions.elementToBeClickable(finishBtn)).click();
    }

    public void clickCancel() {
        wait.until(ExpectedConditions.elementToBeClickable(cancelBtn)).click();
    }

    public double getSubtotal() {
        return parseAmount(wait.until(ExpectedConditions.visibilityOfElementLocated(subtotalLabel)).getText());
    }

    public double getTax() {
        return parseAmount(wait.until(ExpectedConditions.visibilityOfElementLocated(taxLabel)).getText());
    }

    public double getTotal() {
        return parseAmount(wait.until(ExpectedConditions.visibilityOfElementLocated(totalLabel)).getText());
    }

    private double parseAmount(String text) {
        String cleaned = text.replaceAll("[^0-9.]", "");
        return Double.parseDouble(cleaned);
    }

    public String getCompleteHeader() {
        try {
            return driver.findElement(completeHeader).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public String getErrorMessage() {
        try {
            return driver.findElement(errorMsg).getText();
        } catch (Exception e) {
            return "";
        }
    }
}
