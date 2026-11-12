import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';
import { RequestLoanPage } from '../../src/pages/RequestLoanPage';

test.describe('ParaBank UI - Loan Applications', () => {
  test('SCN-LOA-01: Apply for loan with sufficient down payment and verify status @regression', async ({
    page,
    disposableCustomer,
  }) => {
    const { username, password } = disposableCustomer;
    const loginPage = new LoginPage(page);
    const loanPage = new RequestLoanPage(page);

    await loginPage.goto();
    await loginPage.login(username, password);

    await loanPage.goto();
    // Request $1000 loan with $200 down payment (20% threshold)
    const result = await loanPage.applyForLoan(1000, 200);

    expect(['Approved', 'Denied']).toContain(result.status);
    await expect(loanPage.resultContainer).toBeVisible();
  });
});
