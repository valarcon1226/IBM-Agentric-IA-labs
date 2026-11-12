import fs from 'fs';
import path from 'path';
import axios from 'axios';
import { execSync } from 'child_process';

function getConsumerVersion(): string {
  if (process.env.CONSUMER_VERSION) {
    return process.env.CONSUMER_VERSION;
  }
  const timestamp = Math.floor(Date.now() / 1000);
  try {
    const gitHash = execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim();
    return `1.0.0-${gitHash}.${timestamp}`;
  } catch {
    return `1.0.0-${timestamp}`;
  }
}

async function publishPact() {
  const brokerUrl = process.env.PACT_BROKER_BASE_URL || 'http://127.0.0.1:8642';
  const username = process.env.PACT_BROKER_USERNAME || 'pact_user';
  const password = process.env.PACT_BROKER_PASSWORD || 'pact_password';
  const consumerVersion = getConsumerVersion();
  const branch = process.env.CONSUMER_BRANCH || 'main';

  const pactPath = path.resolve(
    process.cwd(),
    'pacts',
    'WebChatWidget-RestaurantAssistantAPI.json',
  );

  if (!fs.existsSync(pactPath)) {
    throw new Error(`Pact file not found at ${pactPath}. Run 'npm run test:consumer' first.`);
  }

  const pactContent = JSON.parse(fs.readFileSync(pactPath, 'utf-8'));
  const consumerName = pactContent.consumer.name;
  const providerName = pactContent.provider.name;

  console.log(
    `Publishing pact for ${consumerName} -> ${providerName} (version ${consumerVersion}) to ${brokerUrl}...`,
  );

  const authHeader = `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}`;

  // 1. Publish pact
  const publishUrl = `${brokerUrl}/pacts/provider/${encodeURIComponent(providerName)}/consumer/${encodeURIComponent(consumerName)}/version/${consumerVersion}`;
  const publishRes = await axios.put(publishUrl, pactContent, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: authHeader,
    },
  });

  console.log(`[OK] Pact published successfully (HTTP ${publishRes.status})`);

  // 2. Tag version
  const tagUrl = `${brokerUrl}/pacticipants/${encodeURIComponent(consumerName)}/versions/${consumerVersion}/tags/${branch}`;
  await axios.put(
    tagUrl,
    {},
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: authHeader,
      },
    },
  );
  console.log(`[OK] Version ${consumerVersion} tagged with '${branch}'`);

  console.log(
    `Pact Broker URL: ${brokerUrl}/pacts/provider/${providerName}/consumer/${consumerName}/version/${consumerVersion}`,
  );
}

publishPact().catch((err) => {
  console.error('[ERROR] Failed to publish pact:', err.response?.data || err.message);
  process.exit(1);
});
