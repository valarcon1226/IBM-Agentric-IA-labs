import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';
import { UpdateProfilePage } from '../../src/pages/UpdateProfilePage';

test.describe('ParaBank UI - Customer Profile', () => {
  test('SCN-PRF-01: Update customer contact information and verify success @regression', async ({
    page,
    disposableCustomer,
  }) => {
    const { username, password } = disposableCustomer;
    const loginPage = new LoginPage(page);
    const profilePage = new UpdateProfilePage(page);

    await loginPage.goto();
    await loginPage.login(username, password);

    await profilePage.goto();
    await profilePage.updatePhoneAndStreet('555-9988', '999 Updated Parkway');

    await expect(profilePage.successMessage).toBeVisible();
    await expect(profilePage.successMessage).toContainText('Profile Updated');
  });
});
