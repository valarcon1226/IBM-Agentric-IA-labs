import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class UpdateProfilePage extends BasePage {
  readonly firstNameInput: Locator;
  readonly lastNameInput: Locator;
  readonly streetInput: Locator;
  readonly cityInput: Locator;
  readonly stateInput: Locator;
  readonly zipCodeInput: Locator;
  readonly phoneNumberInput: Locator;
  readonly submitButton: Locator;
  readonly successMessage: Locator;

  constructor(page: Page) {
    super(page);
    this.firstNameInput = page.locator('input[id="customer.firstName"]');
    this.lastNameInput = page.locator('input[id="customer.lastName"]');
    this.streetInput = page.locator('input[id="customer.address.street"]');
    this.cityInput = page.locator('input[id="customer.address.city"]');
    this.stateInput = page.locator('input[id="customer.address.state"]');
    this.zipCodeInput = page.locator('input[id="customer.address.zipCode"]');
    this.phoneNumberInput = page.locator('input[id="customer.phoneNumber"]');
    this.submitButton = page.locator('input[value="Update Profile"]');
    this.successMessage = page.locator('#updateProfileResult');
  }

  async goto(): Promise<void> {
    await this.page.goto('updateprofile.htm');
    await this.waitForPageLoad();
  }

  async updatePhoneAndStreet(newPhone: string, newStreet: string): Promise<void> {
    await this.phoneNumberInput.waitFor({ state: 'visible' });
    await this.phoneNumberInput.fill(newPhone);
    await this.streetInput.fill(newStreet);
    await this.submitButton.click();
    await this.successMessage.waitFor({ state: 'visible', timeout: 10000 });
  }
}
