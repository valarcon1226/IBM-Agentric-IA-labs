import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';
import { TransferFundsPage } from '../../src/pages/TransferFundsPage';

test.describe('ParaBank UI - Fund Transfers & Balance Reconciliation', () => {
  test('SCN-TRF-01: Transfer funds between accounts via UI and verify confirmation @smoke', async ({
    page,
    disposableCustomer,
  }) => {
    const { username, password, customerId, initialAccountId, apiClient } = disposableCustomer;
    const loginPage = new LoginPage(page);
    const transferPage = new TransferFundsPage(page);

    // Create a second account to transfer funds into
    const targetAccount = await apiClient.createAccount(customerId, 1, initialAccountId);

    await loginPage.goto();
    await loginPage.login(username, password);

    await transferPage.goto();
    const transferAmount = 25.0;
    await transferPage.transferFunds(
      transferAmount,
      String(initialAccountId),
      String(targetAccount.id),
    );

    await expect(transferPage.transferCompleteResult).toBeVisible();
    await expect(transferPage.transferCompleteResult).toContainText('Transfer Complete!');
  });

  test('SCN-TRF-02: Transfer funds via UI and validate balance directly via REST API @regression', async ({
    page,
    disposableCustomer,
  }) => {
    const { username, password, customerId, initialAccountId, apiClient } = disposableCustomer;
    const loginPage = new LoginPage(page);
    const transferPage = new TransferFundsPage(page);

    // 1. Setup: create target account via API
    const targetAccount = await apiClient.createAccount(customerId, 0, initialAccountId);

    // 2. Query initial balances directly via REST API
    const sourceInitial = await apiClient.getAccount(initialAccountId);
    const targetInitial = await apiClient.getAccount(targetAccount.id);

    // 3. Action: Perform transfer via Web UI
    await loginPage.goto();
    await loginPage.login(username, password);

    await transferPage.goto();
    const transferAmount = 75.5;
    await transferPage.transferFunds(
      transferAmount,
      String(initialAccountId),
      String(targetAccount.id),
    );

    // Confirm UI reflects the transfer
    await expect(transferPage.transferCompleteResult).toContainText('Transfer Complete!');

    // 4. Assert: Query backend REST API to verify real balance updates in HSQLDB
    const sourceUpdated = await apiClient.getAccount(initialAccountId);
    const targetUpdated = await apiClient.getAccount(targetAccount.id);

    expect(sourceUpdated.balance).toBeCloseTo(sourceInitial.balance - transferAmount, 2);
    expect(targetUpdated.balance).toBeCloseTo(targetInitial.balance + transferAmount, 2);
  });
});
