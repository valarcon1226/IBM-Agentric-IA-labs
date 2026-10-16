import { Page } from '@playwright/test';

export abstract class BasePage {
  protected readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async waitForPageLoad(): Promise<void> {
    await this.page.waitForLoadState('domcontentloaded');
  }

  async getHeaderTitle(): Promise<string> {
    const heading = this.page.locator('#rightPanel h1.title, #rightPanel h1');
    return (await heading.textContent())?.trim() ?? '';
  }

  async getErrorMessage(): Promise<string> {
    const errorEl = this.page.locator('#rightPanel p.error, .error');
    return (await errorEl.first().textContent())?.trim() ?? '';
  }
}
