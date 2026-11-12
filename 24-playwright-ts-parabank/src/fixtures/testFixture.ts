import { test as base, expect } from '@playwright/test';
import { BankApiClient } from '../api/BankApiClient';
import { BASE_URL } from '../../playwright.config';

export interface DisposableCustomer {
  username: string;
  password: string;
  customerId: number;
  initialAccountId: number;
  apiClient: BankApiClient;
}

export interface TestFixtures {
  apiClient: BankApiClient;
  disposableCustomer: DisposableCustomer;
}

export const test = base.extend<TestFixtures>({
  apiClient: async ({ request }, use) => {
    const client = new BankApiClient(request, BASE_URL);
    await use(client);
  },

  disposableCustomer: async ({ request }, use) => {
    const apiClient = new BankApiClient(request, BASE_URL);
    const rand = Math.floor(Math.random() * 900 + 100);
    const timePart = Date.now().toString().slice(-8);
    const username = `u_${timePart}_${rand}`;
    const password = 'Password123!';

    // Register customer through ParaBank HTTP form flow (maintains session cookie)
    await request.get('register.htm');
    const regResponse = await request.post('register.htm', {
      form: {
        'customer.firstName': 'Fictitious',
        'customer.lastName': 'QAUser',
        'customer.address.street': '123 Fake Street',
        'customer.address.city': 'Metropolis',
        'customer.address.state': 'NY',
        'customer.address.zipCode': '10001',
        'customer.phoneNumber': '555-0199',
        'customer.ssn': '000-00-0000',
        'customer.username': username,
        'customer.password': password,
        repeatedPassword: password,
      },
    });

    expect(regResponse.ok()).toBeTruthy();

    // Query customer profile to retrieve customerId and initial account
    const loginResult = await apiClient.login(username, password);
    expect(loginResult.status).toBe(200);
    const customer = loginResult.customer;
    if (!customer) {
      throw new Error(`Failed to retrieve customer object for registered user: ${username}`);
    }

    const accounts = await apiClient.getCustomerAccounts(customer.id);
    expect(accounts.length).toBeGreaterThan(0);
    const initialAccountId = accounts[0].id;

    // Yield disposable customer to the test
    await use({
      username,
      password,
      customerId: customer.id,
      initialAccountId,
      apiClient,
    });

    // Teardown: Clean database and verify that the dynamic customer was purged
    await apiClient.cleanDb();
    const verifyClean = await apiClient.login(username, password);
    if (verifyClean.status !== 400) {
      throw new Error(
        `Teardown verification failed: Customer ${username} still exists after cleanDB (status ${verifyClean.status})`,
      );
    }
    // cleanDB also removes the seed customer that the API tests use, so restore it.
    const reinit = await apiClient.initializeDb();
    if (!reinit.ok()) {
      throw new Error(`Teardown failed: initializeDB returned HTTP ${reinit.status()}`);
    }
  },
});

export { expect };
