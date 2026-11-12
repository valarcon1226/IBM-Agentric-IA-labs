"""Password reset UI test suite covering normal flow, replay, expiration, and SMTP failure.

Validates:
- OWASP ASVS v4.0.3 Chapter V2 (Authentication Verification - Credential Recovery)
- REQ-IAM-004: Safe password reset handling, anti-enumeration, and resilient retry upon SMTP outage.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable

import httpx
import pytest
from playwright.sync_api import Page
from qa_common.toxiproxy import ToxiproxyClient

MAILPIT_API_URL = "http://127.0.0.1:8025/api/v1"
TOXIPROXY_API_URL = "http://127.0.0.1:8474"


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


def _clear_mailpit_messages() -> None:
    resp = httpx.delete(f"{MAILPIT_API_URL}/messages", timeout=10.0)
    resp.raise_for_status()


def _get_message_count() -> int:
    """Return count of current messages in Mailpit."""
    resp = httpx.get(f"{MAILPIT_API_URL}/messages", timeout=5.0)
    return len(resp.json().get("messages", []))


def _get_latest_email(recipient_contains: str | None = None) -> dict[str, Any]:
    """Retrieve the latest message from Mailpit matching recipient filter."""
    resp = httpx.get(f"{MAILPIT_API_URL}/messages", timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    messages: list[dict[str, Any]] = data.get("messages", [])
    if recipient_contains:
        messages = [
            m
            for m in messages
            if any(recipient_contains in t.get("Address", "") for t in m.get("To", []))
        ]
    assert messages, f"No email found in Mailpit matching filter '{recipient_contains}'"
    msg_id = messages[0]["ID"]
    detail_resp = httpx.get(f"{MAILPIT_API_URL}/message/{msg_id}", timeout=10.0)
    detail_resp.raise_for_status()
    return detail_resp.json()


def _extract_reset_link_from_email(message_detail: dict[str, Any]) -> str:
    """Extract action-token reset URL from plain-text or HTML email body."""
    body_text = message_detail.get("Text", "") + " " + message_detail.get("HTML", "")
    match = re.search(r"http[s]?://\S+/login-actions/action-token\S+", body_text)
    assert match, "Could not extract password reset link from email body"
    raw_url = match.group(0).rstrip('">.,;')
    return raw_url.replace("&amp;", "&")


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-004")
def test_password_reset_happy_path_and_replay_and_expiration(
    edge_page: Page,
    base_url: str,
    realm_name: str,
) -> None:
    """Validate password reset happy path, link replay prevention, and expiration.

    1. Request reset for bench_user_00070.
    2. Read email via Mailpit API and follow action link.
    3. Update password and log in successfully with new password.
    4. Replaying the same link fails ('Action expired').
    5. An expired link (shortened lifespan) fails after configured lifetime.
    """
    admin_token = _get_admin_token(base_url)
    username = "bench_user_00070"
    user_email = f"{username}@example.com"
    new_password = "UpdatedPassword123!"

    _clear_mailpit_messages()

    # Step 1: Request password reset via UI
    reset_url = (
        f"{base_url}/realms/{realm_name}/login-actions/reset-credentials?client_id=account-console"
    )
    edge_page.goto(reset_url)
    edge_page.locator("#username").fill(username)
    edge_page.locator("input[type='submit'], button[type='submit']").click()
    edge_page.wait_for_load_state()

    # Generic notification message displayed
    info_text = edge_page.locator("body").inner_text()
    assert "email" in info_text.lower(), "Expected notification indicating email dispatch"

    # Step 2: Poll Mailpit API with condition wait
    _wait_until_condition(
        lambda: _get_message_count() >= 1,
        timeout_s=10.0,
        interval_s=0.5,
        description="password reset email in Mailpit",
    )
    msg_detail = _get_latest_email(user_email)
    assert "Reset password" in msg_detail.get("Subject", "")
    reset_link = _extract_reset_link_from_email(msg_detail)

    # Step 3: Use reset link to set new password
    edge_page.goto(reset_link)
    edge_page.wait_for_selector("#password-new", timeout=15000)
    edge_page.locator("#password-new").fill(new_password)
    edge_page.locator("#password-confirm").fill(new_password)
    edge_page.locator("input[type='submit'], button[type='submit']").click()
    edge_page.wait_for_load_state()

    # Step 4: Verify login with new password succeeds
    edge_page.context.clear_cookies()
    edge_page.goto(f"{base_url}/realms/{realm_name}/account")
    edge_page.locator("#username").fill(username)
    edge_page.locator("#password").fill(new_password)
    edge_page.locator("#kc-login").click()
    edge_page.wait_for_url(f"{base_url}/realms/{realm_name}/account*", timeout=15000)
    assert f"{base_url}/realms/{realm_name}/account" in edge_page.url

    # Step 5: Reuse the same reset link a second time -> MUST fail
    edge_page.goto(reset_link)
    reused_page_text = edge_page.locator("body").inner_text()
    assert (
        "action expired" in reused_page_text.lower()
        or "invalid" in reused_page_text.lower()
        or "we are sorry" in reused_page_text.lower()
    ), f"Reusing reset link must fail with expired/invalid error, got: {reused_page_text}"
    assert edge_page.locator("#password-new").count() == 0, (
        "Reused reset link must not render password update form"
    )

    # Step 6: Test token expiration with shortened lifespan
    expired_user = "bench_user_00071"
    token_lifespan_seconds = 3

    # Shorten actionTokenGeneratedByUserLifespan in realm
    httpx.put(
        f"{base_url}/admin/realms/{realm_name}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"actionTokenGeneratedByUserLifespan": token_lifespan_seconds},
        timeout=10.0,
    )
    try:
        _clear_mailpit_messages()
        edge_page.context.clear_cookies()
        edge_page.goto(reset_url)
        edge_page.locator("#username").fill(expired_user)
        edge_page.locator("input[type='submit'], button[type='submit']").click()
        edge_page.wait_for_load_state()

        _wait_until_condition(
            lambda: _get_message_count() >= 1,
            timeout_s=10.0,
            interval_s=0.5,
            description="second reset email in Mailpit",
        )
        msg_expired = _get_latest_email(f"{expired_user}@example.com")
        expired_link = _extract_reset_link_from_email(msg_expired)

        # Wait until lifespan expires using condition without sleep
        start_time = time.monotonic()
        _wait_until_condition(
            # Keycloak stores token expiry in whole seconds, so allow a full extra second
            # plus margin; 0.5 s let a still-valid link through on CI.
            lambda: time.monotonic() - start_time > token_lifespan_seconds + 2.0,
            timeout_s=10.0,
            interval_s=0.2,
            description=f"action token lifespan ({token_lifespan_seconds}s) to elapse",
        )

        # Navigate to expired link
        edge_page.goto(expired_link)
        expired_page_text = edge_page.locator("body").inner_text()
        assert (
            "action expired" in expired_page_text.lower()
            or "invalid" in expired_page_text.lower()
            or "we are sorry" in expired_page_text.lower()
        ), f"Expired link must be rejected, got: {expired_page_text}"
        assert edge_page.locator("#password-new").count() == 0, (
            "Expired reset link must not render password update form"
        )
    finally:
        # Restore default lifespan
        httpx.put(
            f"{base_url}/admin/realms/{realm_name}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"actionTokenGeneratedByUserLifespan": 300},
            timeout=10.0,
        )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-004")
def test_password_reset_smtp_down_and_recovery(
    edge_page: Page,
    base_url: str,
    realm_name: str,
) -> None:
    """Validate behavior when SMTP mail server is down and recovery upon restoration.

    1. Cut Toxiproxy SMTP route.
    2. Request reset: assert user sees error message with NO account enumeration leakage.
    3. Assert no email delivered.
    4. Restore Toxiproxy SMTP route.
    5. Retry reset and assert exactly one usable email is delivered.
    """
    toxi = ToxiproxyClient(TOXIPROXY_API_URL)
    username = "bench_user_00072"
    user_email = f"{username}@example.com"
    reset_url = (
        f"{base_url}/realms/{realm_name}/login-actions/reset-credentials?client_id=account-console"
    )

    _clear_mailpit_messages()

    # Cut SMTP route via Toxiproxy
    toxi.set_enabled("smtp", False)

    try:
        edge_page.goto(reset_url)
        edge_page.locator("#username").fill(username)
        edge_page.locator("input[type='submit'], button[type='submit']").click()
        edge_page.wait_for_load_state()

        # Capture user-facing response during SMTP outage
        error_page_text = edge_page.locator("body").inner_text()
        assert (
            "failed to send email" in error_page_text.lower()
            or "we are sorry" in error_page_text.lower()
        ), f"Expected SMTP failure message, got: {error_page_text}"

        # Anti-enumeration verification: response gives NO hint that account exists
        assert username not in error_page_text, (
            "Error page must not leak the requested username (anti-enumeration)"
        )
        assert user_email not in error_page_text, (
            "Error page must not leak user email address (anti-enumeration)"
        )

        # Confirm Mailpit received 0 emails during outage
        messages = httpx.get(f"{MAILPIT_API_URL}/messages", timeout=5.0).json().get("messages", [])
        assert len(messages) == 0, "No emails must be sent while SMTP proxy is disabled"

    finally:
        # Restore SMTP route
        toxi.set_enabled("smtp", True)

    # Retry password reset with SMTP restored
    _clear_mailpit_messages()
    edge_page.goto(reset_url)
    edge_page.locator("#username").fill(username)
    edge_page.locator("input[type='submit'], button[type='submit']").click()
    edge_page.wait_for_load_state()

    # Await exactly one usable email in Mailpit
    _wait_until_condition(
        lambda: _get_message_count() == 1,
        timeout_s=10.0,
        interval_s=0.5,
        description="exactly one email delivered to Mailpit after recovery",
    )

    msg_detail = _get_latest_email(user_email)
    assert "Reset password" in msg_detail.get("Subject", "")
    recovered_link = _extract_reset_link_from_email(msg_detail)

    # Confirm the link is fully usable
    edge_page.goto(recovered_link)
    edge_page.wait_for_selector("#password-new", timeout=15000)
    assert edge_page.locator("#password-new").is_visible()
