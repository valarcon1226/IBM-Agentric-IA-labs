import { Verifier } from '@pact-foundation/pact';
import axios from 'axios';
import { execSync } from 'child_process';

function getProviderVersion(): string {
  if (process.env.PROVIDER_VERSION) {
    return process.env.PROVIDER_VERSION;
  }
  try {
    const gitHash = execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim();
    return `1.0.0-${gitHash}`;
  } catch {
    return `1.0.0-${Date.now()}`;
  }
}

async function verifyProvider() {
  const providerBaseUrl = process.env.PROVIDER_BASE_URL || 'http://127.0.0.1:8004';
  const pactBrokerUrl = process.env.PACT_BROKER_BASE_URL || 'http://127.0.0.1:8642';
  const pactBrokerUsername = process.env.PACT_BROKER_USERNAME || 'pact_user';
  const pactBrokerPassword = process.env.PACT_BROKER_PASSWORD || 'pact_password';
  const providerVersion = getProviderVersion();

  console.log(
    `Starting Provider Verification for RestaurantAssistantAPI against ${pactBrokerUrl}...`,
  );
  console.log(`Target Provider Base URL: ${providerBaseUrl}`);

  // Health check target API before verifying
  try {
    const health = await axios.get(`${providerBaseUrl}/health`, { timeout: 5000 });
    console.log(`[OK] Provider is reachable: ${JSON.stringify(health.data)}`);
  } catch (err: any) {
    console.error(
      `[ERROR] Provider at ${providerBaseUrl} is not reachable! Ensure project 13 is running.`,
    );
    throw err;
  }

  const verifier = new Verifier({
    provider: 'RestaurantAssistantAPI',
    providerBaseUrl,
    pactBrokerUrl,
    pactBrokerUsername,
    pactBrokerPassword,
    publishVerificationResult: true,
    providerVersion,
    providerVersionBranch: 'main',
    consumerVersionTags: ['main'],
    stateHandlers: {
      'the assistant is available': async () => {
        return Promise.resolve('Provider is available');
      },
      'rate limit is exceeded for session': async () => {
        // Send 31 requests to exhaust rate limit for flood_999
        for (let i = 0; i < 31; i++) {
          try {
            await axios.post(`${providerBaseUrl}/web/chat`, {
              session_id: 'flood_999',
              text: `Spam priming ${i}`,
            });
          } catch {
            // expected when hitting 429
          }
        }
        return Promise.resolve('Rate limit induced');
      },
    },
  });

  const output = await verifier.verifyProvider();
  console.log('[OK] Provider Verification Succeeded!');
  console.log(output);
}

verifyProvider().catch((err) => {
  console.error('[ERROR] Provider Verification Failed:', err.message || err);
  process.exit(1);
});
