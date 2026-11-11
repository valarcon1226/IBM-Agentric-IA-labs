import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  DEFAULT_BASE_URL,
  generateWooCommercePayload,
  generateShopifyPayload,
} from './lib/signer.js';

// Instruct k6 that 401 is the expected HTTP response code for this security suite
http.setResponseCallback(http.expectedStatuses(401));

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    'http_req_duration': ['p(95)<200'],
    'http_req_duration{endpoint:wc_invalid_sig}': ['p(95)<200'],
    'http_req_duration{endpoint:shopify_invalid_sig}': ['p(95)<200'],
    'http_req_failed': ['rate==0'],
    'checks': ['rate==1.0'],
  },
};

export default function () {
  const badSignature = 'invalid_hmac_sha256_forged_signature_00000000000=';

  // 1. WooCommerce webhook with invalid HMAC signature
  const wcPayload = generateWooCommercePayload(__VU, __ITER);
  const wcRes = http.post(`${DEFAULT_BASE_URL}/webhooks/woocommerce`, wcPayload, {
    headers: {
      'Content-Type': 'application/json',
      'x-wc-webhook-signature': badSignature,
      'x-wc-webhook-topic': 'order.created',
      'x-wc-webhook-id': `wc_bad_${__VU}_${__ITER}`,
    },
    tags: { endpoint: 'wc_invalid_sig' },
  });

  check(wcRes, {
    'wc signature rejected with 401': (r) => r.status === 401,
  });

  // 2. Shopify webhook with invalid HMAC signature
  const shopifyPayload = generateShopifyPayload(__VU, __ITER);
  const shopifyRes = http.post(`${DEFAULT_BASE_URL}/webhooks/shopify`, shopifyPayload, {
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Hmac-Sha256': badSignature,
      'X-Shopify-Topic': 'orders/create',
      'X-Shopify-Webhook-Id': `shopify_bad_${__VU}_${__ITER}`,
    },
    tags: { endpoint: 'shopify_invalid_sig' },
  });

  check(shopifyRes, {
    'shopify signature rejected with 401': (r) => r.status === 401,
  });

  sleep(0.5);
}
