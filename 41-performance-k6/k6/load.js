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
  adminLogin,
} from './lib/signer.js';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '60s', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'http_req_duration': ['p(95)<600'],
    'http_req_duration{endpoint:webhook_woocommerce}': ['p(95)<500'],
    'http_req_duration{endpoint:webhook_shopify}': ['p(95)<500'],
    'http_req_duration{endpoint:admin_orders}': ['p(95)<600'],
    'http_req_failed': ['rate<0.02'],
    'checks': ['rate>0.98'],
  },
};

export default function () {
  const rand = Math.random();

  if (rand < 0.45) {
    // 1. WooCommerce Order Webhook
    const payload = generateWooCommercePayload(__VU, __ITER);
    const headers = signWooCommerce(payload, DEFAULT_WC_SECRET);
    headers['x-wc-webhook-id'] = `wc_load_${__VU}_${__ITER}_${Date.now()}`;

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
  } else if (rand < 0.90) {
    // 2. Shopify Order Webhook
    const payload = generateShopifyPayload(__VU, __ITER);
    const headers = signShopify(payload, DEFAULT_SHOPIFY_SECRET);
    headers['X-Shopify-Webhook-Id'] = `shopify_load_${__VU}_${__ITER}_${Date.now()}`;

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
  } else {
    // 3. Admin Login & List Orders
    const loginRes = adminLogin(DEFAULT_BASE_URL);
    check(loginRes, {
      'admin login redirects 303': (r) => r.status === 303,
    });

    const ordersRes = http.get(`${DEFAULT_BASE_URL}/admin/orders`, {
      tags: { endpoint: 'admin_orders' },
    });

    check(ordersRes, {
      'admin orders status is 200': (r) => r.status === 200,
      'admin orders page rendered': (r) => r.body && r.body.includes('Pedidos'),
    });
  }

  sleep(1);
}
