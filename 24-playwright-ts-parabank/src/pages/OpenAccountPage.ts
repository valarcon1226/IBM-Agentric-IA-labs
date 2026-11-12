import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class OpenAccountPage extends BasePage {
  readonly accountTypeSelect: Locator;
  readonly fromAccountSelect: Locator;
  readonly submitButton: Locator;
  readonly successResult: Locator;
  readonly newAccountIdLink: Locator;

  constructor(page: Page) {
    super(page);
    this.accountTypeSelect = page.locator('#type');
    this.fromAccountSelect = page.locator('#fromAccountId');
    this.submitButton = page.locator(
      'input[type="submit"][value="Open New Account"], input[value="Open New Account"]',
    );
    this.successResult = page.locator('#openAccountResult');
    this.newAccountIdLink = page.locator('#newAccountId, a#newAccountId');
  }

  async goto(): Promise<void> {
    await this.page.goto('openaccount.htm');
    await this.waitForPageLoad();
  }

  async openAccount(type: 'SAVINGS' | 'CHECKING'): Promise<string> {
    await this.accountTypeSelect.waitFor({ state: 'visible' });
    const optionValue = type === 'SAVINGS' ? '1' : '0';
    await this.accountTypeSelect.selectOption(optionValue);
    // Ensure fromAccountId has options loaded
    await this.fromAccountSelect.waitFor({ state: 'visible' });
    await this.submitButton.click();
    await this.newAccountIdLink.waitFor({ state: 'visible', timeout: 10000 });
    return (await this.newAccountIdLink.textContent())?.trim() ?? '';
  }
}
