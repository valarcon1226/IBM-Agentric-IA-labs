import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';
import { AccountOverviewPage } from '../../src/pages/AccountOverviewPage';
import { OpenAccountPage } from '../../src/pages/OpenAccountPage';
import { FindTransactionsPage } from '../../src/pages/FindTransactionsPage';

test.describe('ParaBank UI - Accounts & Overview', () => {
  test('SCN-ACC-01: Accounts Overview displays account table and total @smoke', async ({
    page,
  }) => {
    const loginPage = new LoginPage(page);
    const overviewPage = new AccountOverviewPage(page);

    await loginPage.goto();
    await loginPage.login('john', 'demo');

    await overviewPage.goto();
    const count = await overviewPage.getAccountCount();
    expect(count).toBeGreaterThan(0);
    await expect(overviewPage.accountTable).toBeVisible();
  });

  test('SCN-ACC-02: View account details from overview table @regression', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const overviewPage = new AccountOverviewPage(page);

    await loginPage.goto();
    await loginPage.login('john', 'demo');

    await overviewPage.goto();
    const firstId = await overviewPage.getFirstAccountId();
    expect(firstId.length).toBeGreaterThan(0);

    await overviewPage.clickAccount(firstId);
    await expect(page).toHaveURL(new RegExp(`activity\\.htm\\?id=${firstId}`));
    await expect(page.locator('#accountId')).toBeVisible();
  });

  test('SCN-OPN-01: Open new savings account and verify new account ID @smoke', async ({
    page,
    disposableCustomer,
  }) => {
    const loginPage = new LoginPage(page);
    const openAccountPage = new OpenAccountPage(page);

    await loginPage.goto();
    await loginPage.login(disposableCustomer.username, disposableCustomer.password);

    await openAccountPage.goto();
    const newAccountId = await openAccountPage.openAccount('SAVINGS');
    expect(newAccountId.length).toBeGreaterThan(0);
    await expect(openAccountPage.successResult).toContainText(
      'Congratulations, your account is now open.',
    );
  });

  test('SCN-FND-01: Find transactions by amount @regression', async ({
    page,
    disposableCustomer,
  }) => {
    const { username, password, initialAccountId, apiClient } = disposableCustomer;
    await apiClient.deposit(initialAccountId, 120.0);

    const loginPage = new LoginPage(page);
    const findPage = new FindTransactionsPage(page);

    await loginPage.goto();
    await loginPage.login(username, password);

    await findPage.goto();
    const count = await findPage.findByAmount(120.0);
    expect(count).toBeGreaterThan(0);
  });
});
