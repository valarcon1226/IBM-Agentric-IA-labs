import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class RequestLoanPage extends BasePage {
  readonly amountInput: Locator;
  readonly downPaymentInput: Locator;
  readonly fromAccountSelect: Locator;
  readonly applyButton: Locator;
  readonly loanStatusText: Locator;
  readonly newAccountIdLink: Locator;
  readonly resultContainer: Locator;

  constructor(page: Page) {
    super(page);
    this.amountInput = page.locator('#amount');
    this.downPaymentInput = page.locator('#downPayment');
    this.fromAccountSelect = page.locator('#fromAccountId');
    this.applyButton = page.locator('input[value="Apply Now"]');
    this.loanStatusText = page.locator('#loanStatus, td#loanStatus');
    this.newAccountIdLink = page.locator('#newAccountId, a#newAccountId');
    this.resultContainer = page.locator('#requestLoanResult');
  }

  async goto(): Promise<void> {
    await this.page.goto('requestloan.htm');
    await this.waitForPageLoad();
  }

  async applyForLoan(
    amount: number,
    downPayment: number,
  ): Promise<{ status: string; newAccountId?: string }> {
    await this.amountInput.waitFor({ state: 'visible' });
    await this.amountInput.fill(amount.toFixed(2));
    await this.downPaymentInput.fill(downPayment.toFixed(2));
    await this.applyButton.click();
    await this.loanStatusText.waitFor({ state: 'visible', timeout: 10000 });
    const status = (await this.loanStatusText.textContent())?.trim() ?? '';
    let newAccountId: string | undefined;
    if (await this.newAccountIdLink.isVisible()) {
      newAccountId = (await this.newAccountIdLink.textContent())?.trim();
    }
    return { status, newAccountId };
  }
}
