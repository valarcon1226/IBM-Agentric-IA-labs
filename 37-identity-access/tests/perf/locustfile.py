"""Locust performance load test for Keycloak OAuth 2.0 endpoints.

Evaluates:
- client_credentials token issuance (service-account client)
- Direct Access Grants (password login) under Argon2 password hashing load
Target SLAs (targets.toml):
- token_p95_at_50rps_ms <= 300.0 ms
- login_p95_at_10rps_ms <= 800.0 ms
"""

from __future__ import annotations

import json
import os
import random
from typing import Any

from locust import HttpUser, between, events, task


class ClientCredentialsUser(HttpUser):
    """Simulates high-throughput M2M client_credentials token requests."""

    wait_time = between(0.01, 0.05)

    @task
    def get_token_client_credentials(self) -> None:
        self.client.post(
            "/realms/identity-realm/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "service-account-client",
                "client_secret": "service-account-secret-1234",
            },
            name="token_client_credentials",
        )


class PasswordLoginUser(HttpUser):
    """Simulates user password authentication (PBKDF2/Argon2 hashing)."""

    wait_time = between(0.05, 0.2)

    @task
    def get_token_password_login(self) -> None:
        user_idx = random.randint(100, 1100)
        username = f"bench_user_{user_idx:05d}"
        self.client.post(
            "/realms/identity-realm/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "confidential-web-app",
                "client_secret": "confidential-secret-1234",
                "username": username,
                "password": "Password123!",
            },
            name="token_password_login",
        )


@events.test_stop.add_listener
def on_test_stop(environment: Any, **kwargs: Any) -> None:
    """Save metrics to results/metrics.json upon Locust completion."""
    os.makedirs("results", exist_ok=True)
    metrics_path = "results/metrics.json"

    current_metrics: dict[str, Any] = {}
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, encoding="utf-8") as f:
                current_metrics = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            current_metrics = {}

    stats = environment.runner.stats
    for name in ["token_client_credentials", "token_password_login"]:
        entry = stats.get(name, "POST")
        if entry and entry.num_requests > 0:
            current_metrics[name] = {
                "count": entry.num_requests,
                "p50_ms": round(entry.get_response_time_percentile(0.50), 2),
                "p95_ms": round(entry.get_response_time_percentile(0.95), 2),
                "p99_ms": round(entry.get_response_time_percentile(0.99), 2),
                "avg_ms": round(entry.avg_response_time, 2),
                "errors": entry.num_failures,
                "error_rate": round(entry.num_failures / entry.num_requests, 4),
            }

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(current_metrics, f, indent=2)
    print(f"\nLocust metrics saved to {metrics_path}")
