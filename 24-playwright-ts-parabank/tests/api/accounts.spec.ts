import { test, expect } from '../../src/fixtures/testFixture';

test.describe('ParaBank REST API - Accounts & Customers', () => {
  test('SCN-API-01: Authenticate baseline customer and validate Customer schema @smoke', async ({
    apiClient,
  }) => {
    const result = await apiClient.login('john', 'demo');
    expect(result.status).toBe(200);
    expect(result.customer).toBeDefined();

    const customer = result.customer!;
    expect(customer.id).toBe(12212);
    expect(customer.firstName).toBe('John');
    expect(customer.lastName).toBe('Smith');
    expect(customer.address).toBeDefined();
    expect(customer.address.street).toBe('1431 Main St');
    expect(customer.address.city).toBe('Beverly Hills');
    expect(customer.address.state).toBe('CA');
    expect(customer.address.zipCode).toBe('90210');
    expect(customer.phoneNumber).toBe('310-447-4121');
    expect(customer.ssn).toBe('622-11-9999');
  });

  test('SCN-API-02: Retrieve customer accounts list and validate Account schema @smoke', async ({
    apiClient,
  }) => {
    const accounts = await apiClient.getCustomerAccounts(12212);
    expect(Array.isArray(accounts)).toBeTruthy();
    expect(accounts.length).toBeGreaterThan(0);

    for (const account of accounts) {
      expect(typeof account.id).toBe('number');
      expect(account.customerId).toBe(12212);
      expect(['CHECKING', 'SAVINGS', 'LOAN']).toContain(account.type);
      expect(typeof account.balance).toBe('number');
    }
  });

  test('SCN-API-03: Query single account details by ID @regression', async ({ apiClient }) => {
    const accounts = await apiClient.getCustomerAccounts(12212);
    expect(accounts.length).toBeGreaterThan(0);
    const targetId = accounts[0].id;

    const account = await apiClient.getAccount(targetId);
    expect(account.id).toBe(targetId);
    expect(account.customerId).toBe(12212);
    expect(account.type).toBe('CHECKING');
    expect(typeof account.balance).toBe('number');
  });

  test('SCN-API-04: Create a new account via API and verify response @regression', async ({
    disposableCustomer,
  }) => {
    const { apiClient, customerId, initialAccountId } = disposableCustomer;

    // Create SAVINGS account (type: 1) transferring from initial account
    const newAccount = await apiClient.createAccount(customerId, 1, initialAccountId);
    expect(newAccount.id).toBeGreaterThan(0);
    expect(newAccount.customerId).toBe(customerId);
    expect(newAccount.type).toBe('SAVINGS');

    // Confirm that the customer now has 2 accounts
    const accounts = await apiClient.getCustomerAccounts(customerId);
    expect(accounts.length).toBe(2);
    expect(accounts.some((a) => a.id === newAccount.id)).toBeTruthy();
  });
});
