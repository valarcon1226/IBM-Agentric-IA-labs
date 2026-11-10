import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';
import { RegisterPage } from '../../src/pages/RegisterPage';

test.describe('ParaBank UI - Authentication & Registration', () => {
  test('SCN-REG-01: Register new customer through registration form @smoke', async ({
    page,
    apiClient,
  }) => {
    const registerPage = new RegisterPage(page);
    const rand = Math.floor(Math.random() * 900 + 100);
    const timePart = Date.now().toString().slice(-8);
    const username = `u_${timePart}_${rand}`;
    const password = 'Password123!';

    await registerPage.goto();
    await registerPage.registerUser({
      firstName: 'Alice',
      lastName: 'Tester',
      street: '789 Testing Way',
      city: 'Austin',
      state: 'TX',
      zipCode: '78701',
      phoneNumber: '555-4321',
      ssn: '123-45-6789',
      username,
      password,
    });

    await expect(registerPage.successMessage).toContainText(
      'Your account was created successfully. You are now logged in.',
    );

    // Teardown: Clean the transient user
    await apiClient.cleanDb();
  });

  test('SCN-REG-02: Registration with missing mandatory fields displays errors @regression', async ({
    page,
  }) => {
    const registerPage = new RegisterPage(page);
    await registerPage.goto();

    // Click register without entering required fields
    await registerPage.submit();

    // Multiple field errors should appear
    await expect(registerPage.fieldErrors.first()).toBeVisible();
    const errorCount = await registerPage.fieldErrors.count();
    expect(errorCount).toBeGreaterThan(0);
  });

  test('SCN-LOG-01: Login with valid credentials redirects to overview @smoke', async ({
    page,
  }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('john', 'demo');

    await expect(page).toHaveURL(/.*overview\.htm/);
    await expect(loginPage.welcomeUserText).toBeVisible();
    await expect(loginPage.welcomeUserText).toContainText('John Smith');
  });

  test('SCN-LOG-02: Login with invalid credentials displays error message @regression', async ({
    page,
  }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('invalid_user_x', 'wrong_pass');

    await expect(loginPage.errorMessage).toBeVisible();
    await expect(loginPage.errorMessage).toContainText(
      'The username and password could not be verified.',
    );
  });

  test('SCN-LOG-04: Logout returns to customer login panel @regression', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('john', 'demo');
    await expect(page).toHaveURL(/.*overview\.htm/);

    await loginPage.logout();
    await expect(loginPage.usernameInput).toBeVisible();
    await expect(loginPage.loginButton).toBeVisible();
  });
});
