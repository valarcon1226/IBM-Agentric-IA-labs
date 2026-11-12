import crypto from 'k6/crypto';
import http from 'k6/http';

export const DEFAULT_BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:8000';
export const DEFAULT_WC_SECRET = __ENV.WOOCOMMERCE_WEBHOOK_SECRET || 'perf_test_woocommerce_secret_key';
export const DEFAULT_SHOPIFY_SECRET = __ENV.SHOPIFY_WEBHOOK_SECRET || 'perf_test_shopify_secret_key';
export const DEFAULT_ADMIN_USER = __ENV.ADMIN_USERNAME || 'admin';
export const DEFAULT_ADMIN_PASS = __ENV.ADMIN_PASSWORD || 'perf_test_admin_password_123';

/**
 * Signs a payload with HMAC-SHA256 Base64 for WooCommerce.
 */
export function signWooCommerce(payloadStr, secret = DEFAULT_WC_SECRET) {
  const sig = crypto.hmac('sha256', secret, payloadStr, 'base64');
  return {
    'Content-Type': 'application/json',
    'x-wc-webhook-signature': sig,
    'x-wc-webhook-topic': 'order.created',
  };
}

/**
 * Signs a payload with HMAC-SHA256 Base64 for Shopify.
 */
export function signShopify(payloadStr, secret = DEFAULT_SHOPIFY_SECRET) {
  const sig = crypto.hmac('sha256', secret, payloadStr, 'base64');
  return {
    'Content-Type': 'application/json',
    'X-Shopify-Hmac-Sha256': sig,
    'X-Shopify-Topic': 'orders/create',
  };
}

/**
 * Generates a globally unique WooCommerce order payload.
 */
export function generateWooCommercePayload(vu, iter) {
  const salt = Math.floor(Math.random() * 9000 + 1000);
  const uniqueNum = Number(`${Date.now() % 100000000}${vu}${salt}`);
  const now = new Date().toISOString();
  return JSON.stringify({
    id: uniqueNum,
    number: String(uniqueNum),
    status: 'processing',
    currency: 'COP',
    date_created: now,
    date_modified: now,
    discount_total: '0.00',
    shipping_total: '0.00',
    total: '86000.00',
    payment_method: 'pse',
    payment_method_title: 'PSE / Transferencia Bancaria',
    billing: {
      first_name: `User${vu}`,
      last_name: `Iter${iter}`,
      company: '',
      address_1: 'Carrera 7 # 72-41',
      city: 'Bogota',
      state: 'Cundinamarca',
      postcode: '110221',
      country: 'CO',
      email: `user_${vu}_${iter}_${salt}@perf.test`,
      phone: '+573001234567',
    },
    shipping: {
      first_name: `User${vu}`,
      last_name: `Iter${iter}`,
      company: '',
      address_1: 'Carrera 7 # 72-41',
      city: 'Bogota',
      state: 'Cundinamarca',
      postcode: '110221',
      country: 'CO',
    },
    line_items: [
      {
        id: 101,
        name: 'Cafe Huila Especial (250g)',
        product_id: 12,
        quantity: 2,
        price: 28000.0,
        subtotal: '56000.00',
        total: '56000.00',
        sku: 'CF-HUI-250',
      },
      {
        id: 102,
        name: 'Cafe Narino Supremo (250g)',
        product_id: 14,
        quantity: 1,
        price: 30000.0,
        subtotal: '30000.00',
        total: '30000.00',
        sku: 'CF-NAR-250',
      },
    ],
  });
}

/**
 * Generates a globally unique Shopify order payload.
 */
export function generateShopifyPayload(vu, iter) {
  const salt = Math.floor(Math.random() * 9000 + 1000);
  const uniqueNum = Number(`${Date.now() % 100000000}${vu}${salt}`);
  const now = new Date().toISOString();
  return JSON.stringify({
    id: uniqueNum,
    name: `#${uniqueNum}`,
    created_at: now,
    updated_at: now,
    financial_status: 'paid',
    fulfillment_status: null,
    currency: 'COP',
    total_price: '55000.00',
    subtotal_price: '55000.00',
    total_tax: '0.00',
    email: `shopify_${vu}_${iter}_${salt}@perf.test`,
    phone: '+573159876543',
    customer: {
      id: uniqueNum,
      first_name: `ShopifyUser${vu}`,
      last_name: `Iter${iter}`,
      email: `shopify_${vu}_${iter}_${salt}@perf.test`,
      phone: '+573159876543',
    },
    shipping_address: {
      first_name: `ShopifyUser${vu}`,
      last_name: `Iter${iter}`,
      address1: 'Calle 10 # 43E-12',
      city: 'Medellin',
      province: 'Antioquia',
      country: 'Colombia',
      zip: '050021',
      country_code: 'CO',
    },
    line_items: [
      {
        id: 9001,
        title: 'Cafe Geisha Sierra Nevada (250g)',
        quantity: 1,
        price: '55000.00',
        sku: 'CF-GEI-250',
        variant_title: 'Grano entero',
      },
    ],
  });
}

/**
 * Authenticates admin via CSRF form and returns the response.
 */
export function adminLogin(baseUrl = DEFAULT_BASE_URL, username = DEFAULT_ADMIN_USER, password = DEFAULT_ADMIN_PASS) {
  const loginPageRes = http.get(`${baseUrl}/admin/login`, {
    tags: { endpoint: 'admin_login_page' },
  });

  const csrfMatch = loginPageRes.body ? loginPageRes.body.match(/name="csrf_token"\s+value="([^"]+)"/) : null;
  const csrfToken = csrfMatch ? csrfMatch[1] : '';

  const postRes = http.post(
    `${baseUrl}/admin/login`,
    {
      username: username,
      password: password,
      csrf_token: csrfToken,
    },
    {
      redirects: 0,
      tags: { endpoint: 'admin_login_submit' },
    }
  );

  return postRes;
}
