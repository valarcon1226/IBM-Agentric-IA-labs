import { test, expect } from '../../src/fixtures/testFixture';
import { LoginPage } from '../../src/pages/LoginPage';

test.describe('ParaBank Visual Regression', () => {
  test('SCN-VIS-01: Compare login panel against baseline snapshot @regression', async ({
    page,
  }) => {
    // ponytail: only a Windows baseline exists; generate a Linux one in the Playwright Docker image to run this in CI.
    test.skip(process.platform !== 'win32', 'Visual baseline exists only for win32');
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    const loginPanel = page.locator('#loginPanel');
    await expect(loginPanel).toBeVisible();

    // Visual comparison with tolerance for cross-platform font rendering
    await expect(loginPanel).toHaveScreenshot('login-panel.png', {
      maxDiffPixelRatio: 0.05,
    });
  });
});
