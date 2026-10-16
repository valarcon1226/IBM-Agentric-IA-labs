import { defineConfig } from 'cypress';
// @ts-expect-error - @cypress/grep plugin exports function
import cypressGrepPlugin from '@cypress/grep/src/plugin';

export function getValidatedBaseUrl(): string {
  const envUrl = process.env.CYPRESS_BASE_URL || 'http://127.0.0.1:8641';
  try {
    const parsed = new URL(envUrl);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(`Invalid protocol in baseUrl: ${parsed.protocol}`);
    }
    return envUrl;
  } catch (error) {
    throw new Error(
      `CYPRESS_BASE_URL must be a valid HTTP/HTTPS URL, received "${envUrl}": ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
  }
}

export default defineConfig({
  e2e: {
    baseUrl: getValidatedBaseUrl(),
    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 15000,
    pageLoadTimeout: 30000,
    video: false,
    screenshotOnRunFailure: true,
    setupNodeEvents(_on, config) {
      cypressGrepPlugin(config);
      return config;
    },
  },
});
