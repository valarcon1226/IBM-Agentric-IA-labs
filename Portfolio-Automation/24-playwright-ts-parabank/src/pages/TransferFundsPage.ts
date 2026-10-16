import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class TransferFundsPage extends BasePage {
  readonly amountInput: Locator;
  readonly fromAccountSelect: Locator;
  readonly toAccountSelect: Locator;
  readonly transferButton: Locator;
  readonly transferCompleteResult: Locator;
  readonly transferredAmountText: Locator;

  constructor(page: Page) {
    super(page);
    this.amountInput = page.locator('#amount');
    this.fromAccountSelect = page.locator('#fromAccountId');
    this.toAccountSelect = page.locator('#toAccountId');
    this.transferButton = page.locator('input[type="submit"][value="Transfer"]');
    this.transferCompleteResult = page.locator('#showResult');
    this.transferredAmountText = page.locator('#amountResult');
  }

  async goto(): Promise<void> {
    await this.page.goto('transfer.htm');
    await this.waitForPageLoad();
  }

  async transferFunds(amount: number, fromAccount?: string, toAccount?: string): Promise<void> {
    await this.amountInput.waitFor({ state: 'visible' });
    await this.amountInput.fill(amount.toFixed(2));
    // Wait until account dropdowns are populated via AJAX
    await this.fromAccountSelect
      .locator('option')
      .first()
      .waitFor({ state: 'attached', timeout: 10000 });
    if (fromAccount) {
      await this.fromAccountSelect.selectOption(fromAccount);
    }
    if (toAccount) {
      await this.toAccountSelect.selectOption(toAccount);
    }
    await this.transferButton.click();
    await this.transferCompleteResult.waitFor({ state: 'visible', timeout: 10000 });
  }
}
