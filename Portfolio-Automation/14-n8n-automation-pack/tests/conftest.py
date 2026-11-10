"""Shared fixtures/constants for the n8n-automation-pack test suite.

Connection settings come from ``E2E_*`` environment variables, falling back to the values in
``.env.example`` (same pattern as ``03-multi-channel-notifier/tests/test_integration_e2e.py`` and
``02-business-registry-enricher``) so the suite can run against a differently-configured stack
without editing test code. Every value is a discrete keyword/placeholder, never a single
credentialed connection string.
"""

import os

N8N_BASE_URL = os.environ.get("E2E_N8N_BASE_URL", "http://localhost:5680")
MAILPIT_BASE_URL = os.environ.get("E2E_MAILPIT_BASE_URL", "http://localhost:8027")
# `webhook-sink` has no published port (internal-only, same as 03-multi-channel-notifier):
# workflows call it over the compose network, tests never assert on it directly.

WEBHOOK_API_KEY = os.environ.get("E2E_WEBHOOK_API_KEY", "change_me_webhook_api_key")
PAYMENT_WEBHOOK_SECRET = os.environ.get(
    "E2E_PAYMENT_WEBHOOK_SECRET", "change_me_payment_webhook_secret"
)

POSTGRES_HOST = os.environ.get("E2E_POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("E2E_POSTGRES_PORT", "5437"))
POSTGRES_USER = os.environ.get("E2E_POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("E2E_POSTGRES_PASSWORD", "change_me_postgres_password")
POSTGRES_DB = os.environ.get("E2E_POSTGRES_DB", "n8n_automation_pack")

HTTP_TIMEOUT_SECONDS = 5.0
