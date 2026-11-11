import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  DEFAULT_BASE_URL,
  DEFAULT_WC_SECRET,
  DEFAULT_SHOPIFY_SECRET,
  signWooCommerce,
  signShopify,
  generateWooCommercePayload,
  generateShopifyPayload,
} from './lib/signer.js';

export const options = {
  stages: [
    { duration: '5s', target: 60 },
    { duration: '20s', target: 60 },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    'http_req_duration': ['p(95)<1500'],
    'http_req_duration{endpoint:webhook_woocommerce}': ['p(95)<1500'],
    'http_req_duration{endpoint:webhook_shopify}': ['p(95)<1500'],
    'http_req_failed': ['rate<0.05'],
    'checks': ['rate>0.95'],
  },
};

export default function () {
  const isWoo = (__VU + __ITER) % 2 === 0;

  if (isWoo) {
    const payload = generateWooCommercePayload(__VU, __ITER);
    const headers = signWooCommerce(payload, DEFAULT_WC_SECRET);
    headers['x-wc-webhook-id'] = `wc_spike_${__VU}_${__ITER}_${Date.now()}`;

    const res = http.post(`${DEFAULT_BASE_URL}/webhooks/woocommerce`, payload, {
      headers: headers,
      tags: { endpoint: 'webhook_woocommerce' },
    });

    check(res, {
      'wc status is 200': (r) => r.status === 200,
      'wc order processed': (r) => {
        if (r.status !== 200) return false;
        try {
          const data = r.json();
          return data && (data.status === 'processed' || data.status === 'ignored');
        } catch {
          return false;
        }
      },
    });
  } else {
    const payload = generateShopifyPayload(__VU, __ITER);
    const headers = signShopify(payload, DEFAULT_SHOPIFY_SECRET);
    headers['X-Shopify-Webhook-Id'] = `shopify_spike_${__VU}_${__ITER}_${Date.now()}`;

    const res = http.post(`${DEFAULT_BASE_URL}/webhooks/shopify`, payload, {
      headers: headers,
      tags: { endpoint: 'webhook_shopify' },
    });

    check(res, {
      'shopify status is 200': (r) => r.status === 200,
      'shopify order processed': (r) => {
        if (r.status !== 200) return false;
        try {
          const data = r.json();
          return data && (data.status === 'processed' || data.status === 'ignored');
        } catch {
          return false;
        }
      },
    });
  }

  sleep(0.5);
}
