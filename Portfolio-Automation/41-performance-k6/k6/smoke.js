import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  DEFAULT_BASE_URL,
  DEFAULT_WC_SECRET,
  signWooCommerce,
  generateWooCommercePayload,
} from './lib/signer.js';

export const options = {
  vus: 1,
  duration: '30s',
  thresholds: {
    'http_req_duration': ['p(95)<300'],
    'http_req_duration{endpoint:health}': ['p(95)<150'],
    'http_req_duration{endpoint:webhook_woocommerce}': ['p(95)<300'],
    'http_req_failed': ['rate<0.01'],
    'checks': ['rate>0.99'],
  },
};

export default function () {
  // 1. GET /health
  const healthRes = http.get(`${DEFAULT_BASE_URL}/health`, {
    tags: { endpoint: 'health' },
  });

  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
    'health body contains healthy': (r) => r.body && r.body.includes('healthy'),
  });

  // 2. Valid WooCommerce webhook
  const payload = generateWooCommercePayload(__VU, __ITER);
  const headers = signWooCommerce(payload, DEFAULT_WC_SECRET);
  headers['x-wc-webhook-id'] = `wc_smoke_${__VU}_${__ITER}_${Date.now()}`;

  const wcRes = http.post(`${DEFAULT_BASE_URL}/webhooks/woocommerce`, payload, {
    headers: headers,
    tags: { endpoint: 'webhook_woocommerce' },
  });

  check(wcRes, {
    'woocommerce status is 200': (r) => r.status === 200,
    'woocommerce is processed': (r) => {
      if (r.status !== 200) return false;
      try {
        const data = r.json();
        return data && (data.status === 'processed' || data.status === 'ignored');
      } catch {
        return false;
      }
    },
  });

  sleep(1);
}
