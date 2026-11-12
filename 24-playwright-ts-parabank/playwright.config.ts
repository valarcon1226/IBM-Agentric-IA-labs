import { defineConfig } from '@playwright/test';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables from .env file
dotenv.config({ path: path.resolve(__dirname, '.env') });

const rawBaseUrl = process.env.BASE_URL ?? 'http://127.0.0.1:8640/parabank';

function validateBaseUrl(urlStr: string): string {
  try {
    const parsed = new URL(urlStr);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(`BASE_URL must use http or https protocol. Received: ${parsed.protocol}`);
    }
    const normalized = urlStr.replace(/\/+$/, '');
    return `${normalized}/`;
  } catch (err) {
    throw new Error(
      `Invalid BASE_URL configured: "${urlStr}". Details: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
}

export const BASE_URL = validateBaseUrl(rawBaseUrl);

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'api',
      testMatch: /.*api\/.*\.spec\.ts/,
    },
    {
      name: 'edge',
      testMatch: /.*(ui|visual)\/.*\.spec\.ts/,
      use: {
        channel: 'msedge',
      },
    },
    {
      name: 'firefox',
      testMatch: /.*ui\/.*\.spec\.ts/,
      use: {
        browserName: 'firefox',
      },
    },
    {
      name: 'webkit',
      testMatch: /.*ui\/.*\.spec\.ts/,
      use: {
        browserName: 'webkit',
      },
    },
  ],
});
