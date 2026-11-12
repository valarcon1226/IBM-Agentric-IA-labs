"""Multi-Factor Authentication (MFA/TOTP) and Brute-Force Lockout UI test suite.

Validates OWASP ASVS v4.0.3 Chapter V2 (Authentication Verification):
- V2.2.1, V2.2.2: Brute-force and credential stuffing protection.
- V2.8.1: Multi-Factor Authentication (TOTP) enrollment and verification.

Tested across Microsoft Edge, Mozilla Firefox, and Apple WebKit.
"""

from __future__ import annotations

import time
from typing import Callable, Generator

import httpx
import pyotp
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright
from qa_common.targets import assert_target

BROWSER_INDEX = {"msedge": 0, "firefox": 1, "webkit": 2}


def _get_admin_token(base_url: str) -> str:
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
    resp = httpx.get(
        f"{base_url}/admin/realms/{realm}/users?username={username}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    users = resp.json()
    assert users, f"User {username} not found in realm {realm}"
    return str(users[0]["id"])


def _reset_user_lockout(base_url: str, realm: str, user_id: str, token: str) -> None:
    resp = httpx.delete(
        f"{base_url}/admin/realms/{realm}/attack-detection/brute-force/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert resp.status_code == 204, f"Failed to reset user lockout: {resp.status_code}"


def _delete_user_otp_credentials(base_url: str, realm: str, user_id: str, token: str) -> None:
    """Delete any existing OTP credentials for a clean slate."""
    resp = httpx.get(
        f"{base_url}/admin/realms/{realm}/users/{user_id}/credentials",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    if resp.status_code == 200:
        for cred in resp.json():
            if cred.get("type") == "otp":
                del_resp = httpx.delete(
                    f"{base_url}/admin/realms/{realm}/users/{user_id}/credentials/{cred['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                assert del_resp.status_code == 204, (
                    f"Failed to delete OTP credential: {del_resp.status_code}"
                )


def _get_attack_detection_status(
    base_url: str, realm: str, user_id: str, token: str
) -> dict[str, object]:
    resp = httpx.get(
        f"{base_url}/admin/realms/{realm}/attack-detection/brute-force/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def _set_realm_lockout_params(
    base_url: str,
    realm: str,
    token: str,
    failure_factor: int = 3,
    wait_increment_seconds: int = 4,
) -> None:
    """Configure brute force parameters for fast, deterministic test execution."""
    resp = httpx.put(
        f"{base_url}/admin/realms/{realm}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "bruteForceProtected": True,
            "permanentLockout": False,
            "failureFactor": failure_factor,
            "waitIncrementSeconds": wait_increment_seconds,
            "minimumQuickLoginWaitSeconds": wait_increment_seconds,
            "maxFailureWaitSeconds": wait_increment_seconds,
            "quickLoginCheckMilliSeconds": 0,
            "maxDeltaTimeSeconds": 43200,
        },
        timeout=10.0,
    )
    assert resp.status_code == 204, f"Failed to update realm lockout config: {resp.status_code}"


def _wait_until_condition(
    condition_fn: Callable[[], bool],
    timeout_s: float = 10.0,
    interval_s: float = 0.5,
    description: str = "condition",
) -> None:
    """Wait on a condition with a timeout, without arbitrary sleeping."""
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout_s:
        if condition_fn():
            return
        time.sleep(interval_s)
    raise TimeoutError(f"Timed out after {timeout_s}s waiting for {description}")


def _ensure_user_has_totp(
    page: Page,
    base_url: str,
    realm_name: str,
    user_id: str,
    username: str,
    password: str,
    admin_token: str,
) -> None:
    """Ensure user has a registered TOTP credential, enrolling if missing."""
    resp = httpx.get(
        f"{base_url}/admin/realms/{realm_name}/users/{user_id}/credentials",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    if resp.status_code == 200:
        for cred in resp.json():
            if cred.get("type") == "otp":
                return

    httpx.put(
        f"{base_url}/admin/realms/{realm_name}/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"requiredActions": ["CONFIGURE_TOTP"]},
        timeout=10.0,
    )
    account_url = f"{base_url}/realms/{realm_name}/account"
    page.goto(account_url)
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()
    page.wait_for_url("**/required-action?execution=CONFIGURE_TOTP*", timeout=15000)
    page.locator("a", has_text="Unable to scan?").click()
    raw_secret = page.locator("#kc-totp-secret-key").inner_text().strip().replace(" ", "").upper()
    totp = pyotp.TOTP(raw_secret)
    code = totp.now()
    page.locator("#totp").fill(code)
    page.locator("#saveTOTPBtn, input[type='submit']").click()
    page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
    page.context.clear_cookies()


@pytest.fixture
def cross_browser_page(
    playwright: Playwright, browser_channel: str
) -> Generator[Page, None, None]:
    """Provide a fresh page on msedge, firefox, or webkit."""
    if browser_channel == "msedge":
        browser: Browser = playwright.chromium.launch(channel="msedge", headless=True)
    elif browser_channel == "firefox":
        browser = playwright.firefox.launch(headless=True)
    elif browser_channel == "webkit":
        browser = playwright.webkit.launch(headless=True)
    else:
        raise ValueError(f"Unsupported browser channel: {browser_channel}")

    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    yield page
    context.close()
    browser.close()


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-001")
@pytest.mark.parametrize("browser_channel", ["msedge", "firefox", "webkit"])
def test_totp_enrollment_and_login_flow(
    cross_browser_page: Page,
    base_url: str,
    realm_name: str,
    browser_channel: str,
) -> None:
    """Enroll TOTP with pyotp from the QR manual secret, log out, and log in with valid code."""
    admin_token = _get_admin_token(base_url)
    idx = BROWSER_INDEX[browser_channel]
    username = f"bench_user_{10 + idx:05d}"
    password = "Password123!"
    user_id = _get_user_id(base_url, realm_name, username, admin_token)

    _delete_user_otp_credentials(base_url, realm_name, user_id, admin_token)
    _reset_user_lockout(base_url, realm_name, user_id, admin_token)

    # Require TOTP configuration
    httpx.put(
        f"{base_url}/admin/realms/{realm_name}/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"requiredActions": ["CONFIGURE_TOTP"]},
        timeout=10.0,
    )

    account_url = f"{base_url}/realms/{realm_name}/account"
    cross_browser_page.goto(account_url)
    cross_browser_page.locator("#username").fill(username)
    cross_browser_page.locator("#password").fill(password)
    cross_browser_page.locator("#kc-login").click()

    # Wait for Mobile Authenticator Setup page
    cross_browser_page.wait_for_url("**/required-action?execution=CONFIGURE_TOTP*", timeout=15000)
    cross_browser_page.locator("a", has_text="Unable to scan?").click()

    raw_secret = cross_browser_page.locator("#kc-totp-secret-key").inner_text().strip()
    clean_secret = raw_secret.replace(" ", "").upper()
    assert clean_secret, "TOTP secret key must not be empty"

    totp = pyotp.TOTP(clean_secret)
    valid_code = totp.now()

    cross_browser_page.locator("#totp").fill(valid_code)
    cross_browser_page.locator("#saveTOTPBtn, input[type='submit']").click()

    # Verifies successful enrollment and navigation to account
    cross_browser_page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
    assert f"{base_url}/realms/{realm_name}/account" in cross_browser_page.url

    # Keycloak enforces TOTP anti-replay: wait for time-step rotation without sleeping
    _wait_until_condition(
        lambda: totp.now() != valid_code,
        timeout_s=35.0,
        interval_s=0.5,
        description="TOTP interval advancement for replay protection",
    )

    # Step 2: Clear context / log out and verify second login prompts for TOTP
    cross_browser_page.context.clear_cookies()
    cross_browser_page.goto(account_url)
    cross_browser_page.locator("#username").fill(username)
    cross_browser_page.locator("#password").fill(password)
    cross_browser_page.locator("#kc-login").click()

    # Now Keycloak prompts for OTP
    cross_browser_page.wait_for_url("**/login-actions/authenticate*", timeout=15000)
    second_code = totp.now()
    cross_browser_page.locator("#otp, #totp, input[name='otp']").fill(second_code)
    cross_browser_page.locator("#kc-login, input[type='submit']").click()

    cross_browser_page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
    assert f"{base_url}/realms/{realm_name}/account" in cross_browser_page.url


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-001")
@pytest.mark.parametrize("browser_channel", ["msedge", "firefox", "webkit"])
def test_wrong_totp_code_counts_as_failure(
    cross_browser_page: Page,
    base_url: str,
    realm_name: str,
    browser_channel: str,
) -> None:
    """A wrong TOTP code counts as a credential failure in brute-force attack detection."""
    admin_token = _get_admin_token(base_url)
    idx = BROWSER_INDEX[browser_channel]
    username = f"bench_user_{20 + idx:05d}"
    password = "Password123!"
    user_id = _get_user_id(base_url, realm_name, username, admin_token)

    _ensure_user_has_totp(
        cross_browser_page, base_url, realm_name, user_id, username, password, admin_token
    )
    _reset_user_lockout(base_url, realm_name, user_id, admin_token)

    account_url = f"{base_url}/realms/{realm_name}/account"
    cross_browser_page.goto(account_url)
    cross_browser_page.locator("#username").fill(username)
    cross_browser_page.locator("#password").fill(password)
    cross_browser_page.locator("#kc-login").click()

    # Wait for OTP prompt
    cross_browser_page.wait_for_url("**/login-actions/authenticate*", timeout=15000)

    # Submit invalid TOTP code
    cross_browser_page.locator("#otp, #totp, input[name='otp']").fill("000000")
    cross_browser_page.locator("#kc-login, input[type='submit']").click()

    # Wait for attack detection failure counter to increment
    _wait_until_condition(
        lambda: _get_attack_detection_status(base_url, realm_name, user_id, admin_token).get(
            "numFailures"
        )
        == 1,
        timeout_s=10.0,
        interval_s=0.2,
        description="attack detection failure count to record wrong TOTP",
    )

    # Error message must be visible
    error_msg = cross_browser_page.locator(".alert, .alert-error, .kc-feedback-text").inner_text()
    assert "invalid" in error_msg.lower(), f"Expected invalid code error message, got: {error_msg}"

    # Verify failure counter incremented in attack detection API
    status = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert status.get("numFailures") == 1, (
        f"Wrong TOTP code must increment numFailures to 1, got: {status.get('numFailures')}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-001")
@pytest.mark.parametrize("browser_channel", ["msedge", "firefox", "webkit"])
def test_lockout_happens_at_exactly_configured_failures(
    cross_browser_page: Page,
    base_url: str,
    realm_name: str,
    browser_channel: str,
) -> None:
    """Lockout triggers at exactly the configured N failures, not one sooner or later."""
    admin_token = _get_admin_token(base_url)
    idx = BROWSER_INDEX[browser_channel]
    username = f"bench_user_{30 + idx:05d}"
    user_id = _get_user_id(base_url, realm_name, username, admin_token)

    # Ensure realm failureFactor is 3 and quick login check disabled to prevent race conditions
    configured_threshold = 3
    _set_realm_lockout_params(
        base_url, realm_name, admin_token, failure_factor=configured_threshold
    )
    _reset_user_lockout(base_url, realm_name, user_id, admin_token)

    account_url = f"{base_url}/realms/{realm_name}/account"

    # Attempt 1: wrong password
    cross_browser_page.goto(account_url)
    cross_browser_page.locator("#username").fill(username)
    cross_browser_page.locator("#password").fill("WrongPassword1!")
    cross_browser_page.locator("#kc-login").click()
    _wait_until_condition(
        lambda: _get_attack_detection_status(base_url, realm_name, user_id, admin_token).get(
            "numFailures"
        )
        == 1,
        timeout_s=10.0,
        interval_s=0.2,
        description="failure count to reach 1",
    )

    status_1 = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert status_1.get("numFailures") == 1, f"Attempt 1 must record 1 failure: {status_1}"
    assert status_1.get("disabled") is False, "User must NOT be locked out after 1 failure"

    # Attempt 2: wrong password
    cross_browser_page.locator("#password").fill("WrongPassword2!")
    cross_browser_page.locator("#kc-login").click()
    _wait_until_condition(
        lambda: _get_attack_detection_status(base_url, realm_name, user_id, admin_token).get(
            "numFailures"
        )
        == 2,
        timeout_s=10.0,
        interval_s=0.2,
        description="failure count to reach 2",
    )

    status_2 = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert status_2.get("numFailures") == 2, f"Attempt 2 must record 2 failures: {status_2}"
    assert status_2.get("disabled") is False, "User must NOT be locked out after 2 failures"

    # Attempt 3: exactly hits configured threshold N = 3
    cross_browser_page.locator("#password").fill("WrongPassword3!")
    cross_browser_page.locator("#kc-login").click()
    _wait_until_condition(
        lambda: _get_attack_detection_status(base_url, realm_name, user_id, admin_token).get(
            "numFailures"
        )
        == 3,
        timeout_s=10.0,
        interval_s=0.2,
        description="failure count to reach 3",
    )

    status_3 = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert status_3.get("numFailures") == 3, f"Attempt 3 must record 3 failures: {status_3}"
    assert status_3.get("disabled") is True, (
        f"Lockout must trigger exactly at configured N={configured_threshold} failures"
    )

    # Validate against targets.toml target
    assert_target("lockout_failure_threshold", float(int(str(status_3["numFailures"]))))


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-001")
@pytest.mark.parametrize("browser_channel", ["msedge", "firefox", "webkit"])
def test_lockout_lasts_configured_time_and_expires(
    cross_browser_page: Page,
    base_url: str,
    realm_name: str,
    browser_channel: str,
) -> None:
    """Lockout lasts the configured time: wait on condition with timeout, no sleep."""
    admin_token = _get_admin_token(base_url)
    idx = BROWSER_INDEX[browser_channel]
    username = f"bench_user_{40 + idx:05d}"
    password = "Password123!"
    user_id = _get_user_id(base_url, realm_name, username, admin_token)

    # Set lockout duration to 4 seconds for fast, non-flaky verification
    lockout_seconds = 4
    _set_realm_lockout_params(
        base_url, realm_name, admin_token, failure_factor=2, wait_increment_seconds=lockout_seconds
    )
    _reset_user_lockout(base_url, realm_name, user_id, admin_token)

    account_url = f"{base_url}/realms/{realm_name}/account"

    # Trigger 2 failures to lock out
    for i in range(2):
        cross_browser_page.goto(account_url)
        cross_browser_page.locator("#username").fill(username)
        cross_browser_page.locator("#password").fill(f"WrongPass_{i}")
        cross_browser_page.locator("#kc-login").click()
        _wait_until_condition(
            lambda: _get_attack_detection_status(base_url, realm_name, user_id, admin_token).get(
                "numFailures"
            )
            == i + 1,
            timeout_s=10.0,
            interval_s=0.2,
            description=f"failure count to reach {i + 1}",
        )

    status_locked = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert status_locked.get("disabled") is True, "User must be locked out"

    # Wait on condition until lockout duration elapses without sleep
    def is_unlocked() -> bool:
        st = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
        return st.get("disabled") is False

    _wait_until_condition(
        is_unlocked,
        timeout_s=lockout_seconds + 5.0,
        interval_s=0.5,
        description=f"temporary lockout expiry ({lockout_seconds}s)",
    )

    # Subsequent login with valid password must succeed
    cross_browser_page.goto(account_url)
    cross_browser_page.locator("#username").fill(username)
    cross_browser_page.locator("#password").fill(password)
    cross_browser_page.locator("#kc-login").click()
    cross_browser_page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
    assert f"{base_url}/realms/{realm_name}/account" in cross_browser_page.url


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-001")
@pytest.mark.parametrize("browser_channel", ["msedge", "firefox", "webkit"])
def test_admin_unlock_via_api(
    cross_browser_page: Page,
    base_url: str,
    realm_name: str,
    browser_channel: str,
) -> None:
    """An admin unlock through the REST API immediately clears lockout."""
    admin_token = _get_admin_token(base_url)
    idx = BROWSER_INDEX[browser_channel]
    username = f"bench_user_{50 + idx:05d}"
    password = "Password123!"
    user_id = _get_user_id(base_url, realm_name, username, admin_token)

    # Set lockout parameters and lock out the user
    _set_realm_lockout_params(
        base_url, realm_name, admin_token, failure_factor=2, wait_increment_seconds=300
    )
    _reset_user_lockout(base_url, realm_name, user_id, admin_token)

    account_url = f"{base_url}/realms/{realm_name}/account"
    for i in range(2):
        cross_browser_page.goto(account_url)
        cross_browser_page.locator("#username").fill(username)
        cross_browser_page.locator("#password").fill(f"WrongPass_{i}")
        cross_browser_page.locator("#kc-login").click()
        _wait_until_condition(
            lambda: _get_attack_detection_status(base_url, realm_name, user_id, admin_token).get(
                "numFailures"
            )
            == i + 1,
            timeout_s=10.0,
            interval_s=0.2,
            description=f"failure count to reach {i + 1}",
        )

    locked_status = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert locked_status.get("disabled") is True, "User must be locked out before admin unlock"

    # Perform Admin Unlock via REST API
    _reset_user_lockout(base_url, realm_name, user_id, admin_token)

    unlocked_status = _get_attack_detection_status(base_url, realm_name, user_id, admin_token)
    assert unlocked_status.get("disabled") is False, "Admin unlock must set disabled=false"
    assert unlocked_status.get("numFailures") == 0, "Admin unlock must reset numFailures to 0"

    # User can now immediately log in
    cross_browser_page.goto(account_url)
    cross_browser_page.locator("#username").fill(username)
    cross_browser_page.locator("#password").fill(password)
    cross_browser_page.locator("#kc-login").click()
    cross_browser_page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
    assert f"{base_url}/realms/{realm_name}/account" in cross_browser_page.url
