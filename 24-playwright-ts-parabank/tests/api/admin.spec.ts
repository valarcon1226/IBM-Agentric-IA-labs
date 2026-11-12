import { test, expect } from '../../src/fixtures/testFixture';

test.describe('ParaBank REST API - Database Lifecycle & Admin', () => {
  test('SCN-API-09: Database reset via cleanDB removes transient accounts @regression', async ({
    apiClient,
    request,
  }) => {
    // 1. Create a dynamic test customer via registration
    const rand = Math.floor(Math.random() * 900 + 100);
    const timePart = Date.now().toString().slice(-8);
    const username = `u_adm_${timePart}_${rand}`;
    const password = 'Password123!';

    await request.get('register.htm');
    const regRes = await request.post('register.htm', {
      form: {
        'customer.firstName': 'Temp',
        'customer.lastName': 'Admin',
        'customer.address.street': '456 Reset Blvd',
        'customer.address.city': 'Denver',
        'customer.address.state': 'CO',
        'customer.address.zipCode': '80202',
        'customer.phoneNumber': '555-9876',
        'customer.ssn': '111-22-3333',
        'customer.username': username,
        'customer.password': password,
        repeatedPassword: password,
      },
    });
    expect(regRes.ok()).toBeTruthy();

    // Confirm that the customer exists
    const beforeClean = await apiClient.login(username, password);
    expect(beforeClean.status).toBe(200);

    // 2. Execute cleanDB
    const cleanRes = await apiClient.cleanDb();
    expect(cleanRes.status()).toBe(204);

    // 3. Confirm that dynamic customer is wiped
    const afterClean = await apiClient.login(username, password);
    expect(afterClean.status).toBe(400);

    // 4. Confirm that baseline user john remains intact
    const johnLogin = await apiClient.login('john', 'demo');
    expect(johnLogin.status).toBe(200);
  });

  test('SCN-API-10: Database initialization via initializeDB restores seed data @regression', async ({
    apiClient,
  }) => {
    const initRes = await apiClient.initializeDb();
    expect(initRes.status()).toBe(204);

    // Verify default customer john is present with expected accounts
    const johnLogin = await apiClient.login('john', 'demo');
    expect(johnLogin.status).toBe(200);
    expect(johnLogin.customer?.id).toBe(12212);

    const accounts = await apiClient.getCustomerAccounts(12212);
    expect(accounts.length).toBeGreaterThanOrEqual(1);
    expect(accounts.some((a) => a.id === 12345)).toBeTruthy();
  });
});
