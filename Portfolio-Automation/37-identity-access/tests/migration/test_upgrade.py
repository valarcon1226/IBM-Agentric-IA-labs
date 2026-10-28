"""Major version upgrade test suite verifying schema migration and credential integrity.

Validates:
- OWASP ASVS v4.0.3 Chapter V14 (Configuration Verification) / REQ-IAM-008.
- Seamless upgrade from Keycloak 25.0.6 (N-1) to Keycloak 26.0.5 (N) over 10,000 users.
- Preservation of client secrets for confidential OAuth 2.0 / OIDC clients.
- Preservation and validity of existing password hashes and enrolled TOTP credentials (20/20 users).
- Post-upgrade OIDC Authorization Code Flow with PKCE S256 and cryptographic ID token validation.
- Rollback documentation via pre-upgrade database snapshot to temporary file.
- Upgrade duration SLA enforcement against targets.toml (target <= 300.0s).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
import jwt
import pyotp
import pytest
from jwt import PyJWKClient
from playwright.sync_api import sync_playwright
from qa_common.targets import assert_target

logger = logging.getLogger("test_upgrade")

COMPOSE_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = COMPOSE_DIR / "results"


def _wait_for_keycloak_ready(timeout: float = 120.0) -> None:
    """Poll Keycloak /health/ready endpoint until HTTP 200 is returned."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            res = httpx.get("http://127.0.0.1:9000/health/ready", timeout=2.0)
            if res.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise TimeoutError(f"Keycloak did not reach ready state within {timeout}s.")


def _set_keycloak_version(version: str) -> None:
    """Switch Keycloak container image version via docker compose."""
    env = os.environ.copy()
    env["KEYCLOAK_VERSION"] = version

    subprocess.run(
        ["docker", "compose", "stop", "keycloak"],
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "rm", "-f", "keycloak"],
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "up", "-d", "keycloak"],
        env=env,
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )


def _start_stack_with_version(version: str) -> None:
    """Start fresh stack with a specific Keycloak version on clean volumes."""
    env = os.environ.copy()
    env["KEYCLOAK_VERSION"] = version

    subprocess.run(
        ["docker", "compose", "down", "-v"],
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "up", "-d"],
        env=env,
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
    )
    _wait_for_keycloak_ready()


def _get_admin_token(base_url: str) -> str:
    """Obtain master realm admin access token."""
    resp = httpx.post(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": "admin",
            "password": "admin",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def _get_user_id(base_url: str, realm: str, username: str, token: str) -> str:
    """Look up user ID by username via Keycloak admin API."""
    resp = httpx.get(
        f"{base_url}/admin/realms/{realm}/users?username={username}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    users = resp.json()
    assert users, f"User {username} not found in realm {realm}"
    return str(users[0]["id"])


def _record_metrics(key: str, data: dict[str, Any]) -> None:
    """Record metrics to results/metrics.json strictly as output."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = RESULTS_DIR / "metrics.json"
    existing: dict[str, Any] = {}
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing[key] = data
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


def _verify_oidc_happy_path(base_url: str, realm_name: str) -> None:
    """Run full OIDC flow with PKCE S256 and cryptographic JWT verification on upgraded server."""
    client_id = "confidential-web-app"
    client_secret = "confidential-secret-1234"
    redirect_uri = "http://127.0.0.1:8000/callback"
    scope = "openid profile email"

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)

    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"{urllib.parse.urlencode(auth_params)}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()

        # Mock callback route so browser captures redirect without 404/connection error
        page.route(f"{redirect_uri}*", lambda route: route.fulfill(status=200, body="Callback OK"))

        page.goto(auth_url)
        page.locator("#username").fill("testuser")
        page.locator("#password").fill("Password123!")
        page.locator("#kc-login").click()
        page.wait_for_url(f"{redirect_uri}*", timeout=15000)
        captured_url = page.url
        browser.close()

    assert captured_url is not None, "Failed to capture redirect URI with authorization code"
    parsed = urllib.parse.urlparse(captured_url)
    qs = urllib.parse.parse_qs(parsed.query)

    auth_code = qs["code"][0]
    returned_state = qs["state"][0]
    assert returned_state == state, "Returned state does not match sent state"

    # Token exchange with PKCE verifier
    token_resp = httpx.post(
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        timeout=10.0,
    )
    assert token_resp.status_code == 200, f"Token exchange failed: {token_resp.text}"
    token_data = token_resp.json()
    id_token = token_data.get("id_token")
    assert id_token, "No id_token in token response"

    # Cryptographic verification against realm JWKS
    jwks_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/certs"
    jwks_client = PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=f"{base_url}/realms/{realm_name}",
        options={"require": ["exp", "iss", "aud", "sub", "nonce"]},
    )

    assert claims.get("nonce") == nonce, "ID token nonce does not match requested nonce"
    assert claims.get("preferred_username") == "testuser"


@pytest.mark.p1
@pytest.mark.migration
@pytest.mark.req("REQ-IAM-008")
def test_keycloak_major_version_upgrade_25_to_26(base_url: str, realm_name: str) -> None:
    """Execute major version upgrade from Keycloak 25.0.6 to 26.0.5 on a fresh database.

    Steps:
    1. Start Keycloak 25.0.6 on a fresh database.
    2. Seed 10,000 baseline users using scripts/seed_users.py.
    3. Enroll TOTP for 20 users and keep their secrets in memory.
    4. pg_dump to a temporary file and assert it is non-empty.
    5. Switch Keycloak image to 26.0.5, time until /health/ready.
    6. Verify client secrets are preserved post-upgrade.
    7. Authenticate all 20 users with password and TOTP against Keycloak 26.0.5.
    8. Run full OIDC Authorization Code Flow with PKCE S256 on upgraded server.
    9. Write metrics to results/metrics.json and assert upgrade duration SLA (<= 300s).
    """
    # 1. Start Keycloak 25.0.6 on a fresh database
    _start_stack_with_version("25.0.6")

    # 2. Seed 10,000 users using scripts/seed_users.py
    seed_proc = subprocess.run(
        [sys.executable, str(COMPOSE_DIR / "scripts" / "seed_users.py")],
        cwd=str(COMPOSE_DIR),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "10000" in seed_proc.stdout, f"Expected 10,000 users seeded, output: {seed_proc.stdout}"

    # 3. Enroll TOTP for 20 users and keep their secrets in memory
    totp_secrets: dict[str, str] = {}
    admin_token = _get_admin_token(base_url)

    # Configure CONFIGURE_TOTP required action for the first 20 benchmark users
    for i in range(1, 21):
        username = f"bench_user_{i:05d}"
        user_id = _get_user_id(base_url, realm_name, username, admin_token)
        req_resp = httpx.put(
            f"{base_url}/admin/realms/{realm_name}/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"requiredActions": ["CONFIGURE_TOTP"]},
            timeout=10.0,
        )
        req_resp.raise_for_status()

    # Complete TOTP enrollment via browser and capture secrets in memory
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for i in range(1, 21):
            username = f"bench_user_{i:05d}"
            context = browser.new_context()
            page = context.new_page()

            account_url = f"{base_url}/realms/{realm_name}/account"
            page.goto(account_url)
            page.locator("#username").fill(username)
            page.locator("#password").fill("Password123!")
            page.locator("#kc-login").click()

            page.wait_for_url("**/required-action?execution=CONFIGURE_TOTP*", timeout=15000)
            page.locator("a", has_text="Unable to scan?").click()
            raw_secret = page.locator("#kc-totp-secret-key").inner_text()
            clean_secret = re.sub(r"\s+", "", raw_secret).upper()
            assert clean_secret, f"TOTP secret key must not be empty for {username}"
            totp_secrets[username] = clean_secret

            totp = pyotp.TOTP(clean_secret)
            code = totp.now()
            page.locator("#totp").fill(code)
            page.locator("#saveTOTPBtn").click()

            page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
            context.close()

        browser.close()

    assert len(totp_secrets) == 20, f"Expected 20 enrolled TOTP secrets, got {len(totp_secrets)}"

    # 4. pg_dump to a temporary file and assert it is non-empty
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp_file:
        temp_snapshot_path = Path(tmp_file.name)

    try:
        dump_proc = subprocess.run(
            ["docker", "exec", "identity-postgres", "pg_dump", "-U", "keycloak", "keycloak"],
            check=True,
            capture_output=True,
        )
        temp_snapshot_path.write_bytes(dump_proc.stdout)
        snapshot_size = temp_snapshot_path.stat().st_size
        assert snapshot_size > 0, "Pre-upgrade database snapshot must be non-empty"
    finally:
        if temp_snapshot_path.exists():
            temp_snapshot_path.unlink()

    # 5. Switch to 26.0.5, time until /health/ready
    t_upgrade_start = time.monotonic()
    _set_keycloak_version("26.0.5")
    _wait_for_keycloak_ready(timeout=300.0)
    upgrade_duration_seconds = round(time.monotonic() - t_upgrade_start, 2)

    # 6. Check client secrets post-upgrade
    admin_token_post = _get_admin_token(base_url)
    headers = {"Authorization": f"Bearer {admin_token_post}"}

    clients_resp = httpx.get(
        f"{base_url}/admin/realms/{realm_name}/clients?clientId=confidential-web-app",
        headers=headers,
        timeout=10.0,
    )
    clients_resp.raise_for_status()
    clients = clients_resp.json()
    assert clients, "Client 'confidential-web-app' not found post-upgrade"
    client_id = clients[0]["id"]

    secret_resp = httpx.get(
        f"{base_url}/admin/realms/{realm_name}/clients/{client_id}/client-secret",
        headers=headers,
        timeout=10.0,
    )
    secret_resp.raise_for_status()
    actual_secret = secret_resp.json().get("value")
    expected_secret = "confidential-secret-1234"
    assert actual_secret == expected_secret, (
        f"Client secret mismatch! Expected '{expected_secret}', got '{actual_secret}'"
    )

    # 7. Log in all 20 users with password and TOTP
    successful_logins = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for username, b32_secret in totp_secrets.items():
            totp = pyotp.TOTP(b32_secret)
            context = browser.new_context()
            page = context.new_page()

            account_url = f"{base_url}/realms/{realm_name}/account"
            page.goto(account_url)
            page.locator("#username").fill(username)
            page.locator("#password").fill("Password123!")
            page.locator("#kc-login").click()

            # Expect OTP challenge prompt
            page.wait_for_selector("#otp, #totp, input[name='otp']", timeout=15000)
            code = totp.now()
            page.locator("#otp, #totp, input[name='otp']").fill(code)
            page.locator("#kc-login, input[type='submit']").click()

            # Confirm navigation to account console with domcontentloaded
            page.wait_for_url("**/account*", wait_until="domcontentloaded", timeout=15000)
            assert f"{base_url}/realms/{realm_name}/account" in page.url
            context.close()
            successful_logins += 1

        browser.close()

    assert successful_logins == 20, f"Expected 20 successful logins, got {successful_logins}"

    # 8. Post-upgrade OIDC flow with PKCE and RS256 token verification
    _verify_oidc_happy_path(base_url, realm_name)

    # 9. Record metrics to results/ strictly as output and assert target
    _record_metrics(
        "schema_migration",
        {
            "upgrade_duration_seconds": upgrade_duration_seconds,
            "previous_version": "25.0.6",
            "target_version": "26.0.5",
            "total_users": 10000,
            "enrolled_totp_users": len(totp_secrets),
            "successful_logins": successful_logins,
            "client_secrets_matched": True,
        },
    )

    assert_target("upgrade_duration_seconds", upgrade_duration_seconds)
