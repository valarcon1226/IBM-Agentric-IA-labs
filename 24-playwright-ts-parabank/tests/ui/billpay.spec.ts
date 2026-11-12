import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';
import { BillPayPage } from '../../src/pages/BillPayPage';

test.describe('ParaBank UI - Bill Pay', () => {
  test('SCN-BIL-01: Pay bill to utility company and verify payment confirmation @regression', async ({
    page,
    disposableCustomer,
  }) => {
    const { username, password } = disposableCustomer;
    const loginPage = new LoginPage(page);
    const billPayPage = new BillPayPage(page);

    await loginPage.goto();
    await loginPage.login(username, password);

    await billPayPage.goto();
    await billPayPage.payBill({
      payeeName: 'Electric City Energy',
      street: '400 Grid Lane',
      city: 'Chicago',
      state: 'IL',
      zipCode: '60601',
      phoneNumber: '555-8899',
      accountNumber: '987654',
      amount: 45.0,
    });

    await expect(billPayPage.successResult).toBeVisible();
    await expect(billPayPage.successResult).toContainText('Bill Payment Complete');
  });
});
