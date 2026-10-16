import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class LoginPage extends BasePage {
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly loginButton: Locator;
  readonly registerLink: Locator;
  readonly forgotLoginLink: Locator;
  readonly welcomeUserText: Locator;
  readonly logoutLink: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);
    this.usernameInput = page.locator('input[name="username"]');
    this.passwordInput = page.locator('input[name="password"]');
    this.loginButton = page.locator('input[type="submit"][value="Log In"]');
    this.registerLink = page.locator('a[href*="register.htm"]');
    this.forgotLoginLink = page.locator('a[href*="lookup.htm"]');
    this.welcomeUserText = page.locator('#leftPanel p.smallText');
    this.logoutLink = page.locator('a[href*="logout.htm"]');
    this.errorMessage = page.locator('#rightPanel p.error');
  }

  async goto(): Promise<void> {
    await this.page.goto('index.htm');
    await this.waitForPageLoad();
  }

  async login(username: string, pass: string): Promise<void> {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(pass);
    await this.loginButton.click();
    await Promise.race([
      this.page.waitForURL(/.*overview\.htm/),
      this.errorMessage.waitFor({ state: 'visible' }),
    ]).catch(() => {});
  }

  async navigateToRegister(): Promise<void> {
    await this.registerLink.click();
    await this.waitForPageLoad();
  }

  async logout(): Promise<void> {
    await this.logoutLink.click();
    await this.waitForPageLoad();
  }

  async isLoggedIn(): Promise<boolean> {
    return this.welcomeUserText.isVisible();
  }
}
