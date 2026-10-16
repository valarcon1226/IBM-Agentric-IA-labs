import axios from 'axios';

async function canIDeploy() {
  const brokerUrl = process.env.PACT_BROKER_BASE_URL || 'http://127.0.0.1:8642';
  const username = process.env.PACT_BROKER_USERNAME || 'pact_user';
  const password = process.env.PACT_BROKER_PASSWORD || 'pact_password';
  const pacticipant = process.env.PACTICIPANT || 'WebChatWidget';

  console.log(`Checking can-i-deploy for ${pacticipant} in Pact Broker (${brokerUrl})...`);

  const authHeader = `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}`;

  const matrixUrl = `${brokerUrl}/matrix?q[][pacticipant]=${encodeURIComponent(pacticipant)}&q[][latest]=true`;

  const res = await axios.get(matrixUrl, {
    headers: {
      Authorization: authHeader,
      Accept: 'application/hal+json, application/json, */*',
    },
  });

  const summary = res.data.summary;
  console.log('--------------------------------------------------');
  console.log(`CAN-I-DEPLOY RESULT: ${summary.deployable ? 'SUCCESS (DEPLOYABLE)' : 'BLOCKED'}`);
  console.log(`Success verifications: ${summary.success}`);
  console.log(`Failed verifications:  ${summary.failed}`);
  console.log(`Unknown verifications: ${summary.unknown}`);
  console.log(`Reason: ${summary.reason}`);
  console.log('--------------------------------------------------');

  if (!summary.deployable) {
    console.error(`[BLOCKED] ${pacticipant} is not safe to deploy!`);
    process.exit(1);
  } else {
    console.log(`[OK] ${pacticipant} is certified and ready to deploy to production.`);
  }
}

canIDeploy().catch((err) => {
  console.error('[ERROR] can-i-deploy check failed:', err.response?.data || err.message);
  process.exit(1);
});
