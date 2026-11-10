import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class FindTransactionsPage extends BasePage {
  readonly accountSelect: Locator;
  readonly transactionIdInput: Locator;
  readonly findByIdButton: Locator;
  readonly dateInput: Locator;
  readonly findByDateButton: Locator;
  readonly fromDateInput: Locator;
  readonly toDateInput: Locator;
  readonly findByDateRangeButton: Locator;
  readonly amountInput: Locator;
  readonly findByAmountButton: Locator;
  readonly transactionTable: Locator;
  readonly transactionRows: Locator;

  constructor(page: Page) {
    super(page);
    this.accountSelect = page.locator('#accountId');
    this.transactionIdInput = page.locator('#transactionId');
    this.findByIdButton = page.locator('button#findById');
    this.dateInput = page.locator('#transactionDate');
    this.findByDateButton = page.locator('button#findByDate');
    this.fromDateInput = page.locator('#fromDate');
    this.toDateInput = page.locator('#toDate');
    this.findByDateRangeButton = page.locator('button#findByDateRange');
    this.amountInput = page.locator('#amount');
    this.findByAmountButton = page.locator('button#findByAmount');
    this.transactionTable = page.locator('#transactionTable');
    this.transactionRows = page.locator('#transactionTable tbody tr');
  }

  async goto(): Promise<void> {
    await this.page.goto('findtrans.htm');
    await this.waitForPageLoad();
  }

  async findByAmount(amount: number): Promise<number> {
    await this.amountInput.waitFor({ state: 'visible' });
    await this.amountInput.fill(amount.toFixed(2));
    await this.findByAmountButton.click();
    await this.transactionTable.waitFor({ state: 'visible', timeout: 10000 });
    return this.transactionRows.count();
  }
}
