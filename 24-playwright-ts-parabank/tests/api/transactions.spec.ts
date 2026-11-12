import { test, expect } from '../../src/fixtures/testFixture';

test.describe('ParaBank REST API - Transactions & Funds', () => {
  test('SCN-API-05: Deposit funds into account and verify balance updated @regression', async ({
    disposableCustomer,
  }) => {
    const { apiClient, initialAccountId } = disposableCustomer;

    const initialAccount = await apiClient.getAccount(initialAccountId);
    const depositAmount = 250.0;

    const responseText = await apiClient.deposit(initialAccountId, depositAmount);
    expect(responseText).toContain('Successfully deposited $');
    expect(responseText).toContain(`to account #${initialAccountId}`);

    const updatedAccount = await apiClient.getAccount(initialAccountId);
    expect(updatedAccount.balance).toBeCloseTo(initialAccount.balance + depositAmount, 2);
  });

  test('SCN-API-06: Transfer funds between accounts via API and verify both balances @regression', async ({
    disposableCustomer,
  }) => {
    const { apiClient, customerId, initialAccountId } = disposableCustomer;

    // Create a target account for transfer
    const targetAccount = await apiClient.createAccount(customerId, 0, initialAccountId);
    const transferAmount = 100.0;

    const sourceBefore = await apiClient.getAccount(initialAccountId);
    const targetBefore = await apiClient.getAccount(targetAccount.id);

    const message = await apiClient.transfer(initialAccountId, targetAccount.id, transferAmount);
    expect(message).toContain('Successfully transferred $');
    expect(message).toContain(`from account #${initialAccountId} to account #${targetAccount.id}`);

    const sourceAfter = await apiClient.getAccount(initialAccountId);
    const targetAfter = await apiClient.getAccount(targetAccount.id);

    expect(sourceAfter.balance).toBeCloseTo(sourceBefore.balance - transferAmount, 2);
    expect(targetAfter.balance).toBeCloseTo(targetBefore.balance + transferAmount, 2);
  });

  test('SCN-API-07: Retrieve transactions history for an account @regression', async ({
    disposableCustomer,
  }) => {
    const { apiClient, initialAccountId } = disposableCustomer;

    // Perform a deposit to guarantee at least one transaction exists on the disposable account
    await apiClient.deposit(initialAccountId, 125.0);

    const transactions = await apiClient.getAccountTransactions(initialAccountId);
    expect(Array.isArray(transactions)).toBeTruthy();
    expect(transactions.length).toBeGreaterThan(0);

    const tx = transactions[0];
    expect(tx.accountId).toBe(initialAccountId);
    expect(['Credit', 'Debit']).toContain(tx.type);
    expect(typeof tx.amount).toBe('number');
    expect(typeof tx.description).toBe('string');
  });

  test('SCN-API-08: Request a loan via API and validate LoanResponse schema @regression', async ({
    disposableCustomer,
  }) => {
    const { apiClient, customerId, initialAccountId } = disposableCustomer;

    const loanResponse = await apiClient.requestLoan(customerId, 1000, 200, initialAccountId);
    expect(typeof loanResponse.approved).toBe('boolean');
    expect(typeof loanResponse.loanProviderName).toBe('string');
    expect(['string', 'number']).toContain(typeof loanResponse.responseDate);
    if (loanResponse.approved) {
      expect(loanResponse.accountId).toBeDefined();
    }
  });
});
