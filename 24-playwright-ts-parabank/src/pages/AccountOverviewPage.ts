import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class AccountOverviewPage extends BasePage {
  readonly accountTable: Locator;
  readonly accountRows: Locator;
  readonly accountLinks: Locator;
  readonly totalBalanceCell: Locator;

  constructor(page: Page) {
    super(page);
    this.accountTable = page.locator('#accountTable');
    this.accountRows = page.locator('#accountTable tbody tr');
    this.accountLinks = page.locator('#accountTable tbody tr td a');
    this.totalBalanceCell = page.locator(
      '#accountTable tr:has-text("Total") td.ng-binding, #accountTable tfoot td:last-child',
    );
  }

  async goto(): Promise<void> {
    await this.page.goto('overview.htm');
    await this.waitForPageLoad();
  }

  async getAccountCount(): Promise<number> {
    await this.accountTable.waitFor({ state: 'visible' });
    return this.accountLinks.count();
  }

  async getFirstAccountId(): Promise<string> {
    await this.accountTable.waitFor({ state: 'visible' });
    const firstLink = this.accountLinks.first();
    return (await firstLink.textContent())?.trim() ?? '';
  }

  async clickAccount(accountId: string): Promise<void> {
    await this.page.locator(`#accountTable a:text("${accountId}")`).click();
    await this.waitForPageLoad();
  }
}
