"""OAuth 2.0 and OpenID Connect retry and replay security verification suite.

Evaluates RFC 6749 (The OAuth 2.0 Authorization Framework) and
RFC 9700 (OAuth 2.0 Security Best Current Practice) requirements
against Keycloak 26.0.5 token exchange, rotation, and revocation endpoints.
"""

from __future__ import annotations

import asyncio
import secrets
import urllib.parse

import httpx
import pytest
from playwright.sync_api import Page


def _get_auth_code(
    page: Page,
    base_url: str,
    realm_name: str,
    client_id: str,
    redirect_uri: str,
    challenge: str,
) -> str:
    """Drive login flow on Edge and extract code from redirect callback."""
    page.route(f"{redirect_uri}*", lambda route: route.fulfill(status=200, body="OK"))
    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope=openid&"
        f"state={secrets.token_urlsafe(16)}&"
        f"nonce={secrets.token_urlsafe(16)}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )
    page.goto(auth_url)
    page.locator("#username").fill("testuser")
    page.locator("#password").fill("Password123!")
    page.locator("#kc-login").click()
    page.wait_for_url(f"{redirect_uri}*", timeout=15000)

    qs = urllib.parse.parse_qs(urllib.parse.urlparse(page.url).query)
    code = qs.get("code")
    assert code, "Authorization code must be present in redirect callback (RFC 6749 §4.1.2)"
    return code[0]


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-002")
def test_authorization_code_replayed_returns_invalid_grant_and_revokes_tokens(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """Exchange code twice: second exchange fails with invalid_grant and revokes original tokens.

    References:
    - RFC 6749 §4.1.2: "The client MUST NOT use the authorization code more than once.
      If an authorization code is used more than once, the authorization server MUST deny
      the request and SHOULD revoke all tokens previously issued based on that code."
    - RFC 9700 §2.1.1: "Authorization servers MUST ensure that authorization codes are
      single-use. If an authorization code is used more than once, the authorization server
      MUST revoke all tokens previously issued based on that authorization code."
    """
    verifier, challenge = pkce_pair
    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    code = _get_auth_code(
        page=edge_page,
        base_url=base_url,
        realm_name=realm_name,
        client_id=client_id,
        redirect_uri=redirect_uri,
        challenge=challenge,
    )

    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }

    # First exchange must succeed
    first_resp = httpx.post(token_url, data=token_payload, timeout=10.0)
    assert first_resp.status_code == 200, (
        f"Initial code exchange failed unexpectedly: {first_resp.text} (RFC 6749 §4.1.3)"
    )
    tokens = first_resp.json()
    access_token = tokens["access_token"]
    assert access_token, "access_token must be issued upon first exchange (RFC 6749 §5.1)"

    # Second exchange (replay) MUST be rejected with HTTP 400 invalid_grant
    replay_resp = httpx.post(token_url, data=token_payload, timeout=10.0)
    assert replay_resp.status_code == 400, (
        f"Replayed authorization code must return HTTP 400 (RFC 6749 §5.2), "
        f"got {replay_resp.status_code}"
    )
    error_data = replay_resp.json()
    assert error_data.get("error") == "invalid_grant", (
        f"Replayed authorization code must yield 'invalid_grant' (RFC 6749 §5.2), "
        f"got: {error_data.get('error')}"
    )

    # Introspect original access_token: Keycloak 26 revokes tokens upon detected code replay
    introspect_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token/introspect"
    intro_resp = httpx.post(
        introspect_url,
        data={"token": access_token},
        auth=(client_id, client_secret),
        timeout=10.0,
    )
    assert intro_resp.status_code == 200, (
        f"Token introspection endpoint must respond with HTTP 200 (RFC 7662 §2.2), "
        f"got: {intro_resp.status_code}"
    )
    intro_data = intro_resp.json()
    assert intro_data.get("active") is False, (
        f"Tokens issued from replayed code must be revoked and report active=false "
        f"(RFC 9700 §2.1.1 and Keycloak 26 documentation), got: {intro_data}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-002")
def test_refresh_token_rotation_and_old_token_reuse_revokes_session(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """When refresh-token rotation is on, reusing an old refresh token fails and revokes session.

    References:
    - RFC 6749 §6: "The authorization server MAY issue a new refresh token, in which case
      the client MUST discard the old refresh token and replace it with the new refresh token."
    - RFC 9700 §4.14.2: "When refresh token rotation is used, the authorization server MUST
      revoke the previous refresh token when issuing a new one. If a previously invalidated
      refresh token is presented, the authorization server MUST invalidate the refresh token
      family and terminate the user session."
    """
    verifier, challenge = pkce_pair
    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    code = _get_auth_code(
        page=edge_page,
        base_url=base_url,
        realm_name=realm_name,
        client_id=client_id,
        redirect_uri=redirect_uri,
        challenge=challenge,
    )

    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"

    # Step 1: Initial token exchange
    init_resp = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        timeout=10.0,
    )
    assert init_resp.status_code == 200, (
        f"Initial token exchange failed (RFC 6749 §4.1.3): {init_resp.text}"
    )
    old_refresh_token = init_resp.json()["refresh_token"]
    assert old_refresh_token, "Refresh token must be returned in initial response (RFC 6749 §5.1)"

    # Step 2: Refresh once using old_refresh_token
    refresh_1_resp = httpx.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": old_refresh_token,
        },
        timeout=10.0,
    )
    assert refresh_1_resp.status_code == 200, (
        f"First refresh token exchange failed (RFC 6749 §6): {refresh_1_resp.text}"
    )
    tokens_refreshed = refresh_1_resp.json()
    new_access_token = tokens_refreshed["access_token"]
    new_refresh_token = tokens_refreshed["refresh_token"]

    assert new_refresh_token != old_refresh_token, (
        "Rotated refresh token must differ from old refresh token (RFC 9700 §4.14.2)"
    )

    # Step 3: Reuse old_refresh_token - MUST fail with invalid_grant
    reuse_resp = httpx.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": old_refresh_token,
        },
        timeout=10.0,
    )
    assert reuse_resp.status_code == 400, (
        f"Reused refresh token must return HTTP 400 (RFC 6749 §5.2), got {reuse_resp.status_code}"
    )
    error_data = reuse_resp.json()
    assert error_data.get("error") == "invalid_grant", (
        f"Reused refresh token must yield 'invalid_grant' (RFC 6749 §5.2), "
        f"got: {error_data.get('error')}"
    )

    # Step 4: Introspection on new_access_token must show session revoked
    introspect_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token/introspect"
    intro_resp = httpx.post(
        introspect_url,
        data={"token": new_access_token},
        auth=(client_id, client_secret),
        timeout=10.0,
    )
    assert intro_resp.status_code == 200, (
        f"Introspection endpoint must return HTTP 200 (RFC 7662 §2.2), got {intro_resp.status_code}"
    )
    intro_data = intro_resp.json()
    assert intro_data.get("active") is False, (
        f"Session must be revoked upon refresh token reuse detection, "
        f"active=false required (RFC 9700 §4.14.2), got: {intro_data}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-002")
def test_parallel_refreshes_behavior_documented(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """Run two refreshes concurrently with asyncio and document outcome.

    References:
    - RFC 6749 §6: Refresh token semantics under concurrency.
    - RFC 9700 §4.14.2: Handling concurrent client refreshes under token rotation.
    """
    verifier, challenge = pkce_pair
    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    code = _get_auth_code(
        page=edge_page,
        base_url=base_url,
        realm_name=realm_name,
        client_id=client_id,
        redirect_uri=redirect_uri,
        challenge=challenge,
    )

    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"
    init_resp = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        timeout=10.0,
    )
    assert init_resp.status_code == 200, (
        f"Initial token exchange failed (RFC 6749 §4.1.3): {init_resp.text}"
    )
    refresh_token = init_resp.json()["refresh_token"]

    async def execute_parallel() -> tuple[httpx.Response, httpx.Response]:
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient() as client:
            r1, r2 = await asyncio.gather(
                client.post(token_url, data=data),
                client.post(token_url, data=data),
            )
            return r1, r2

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        resp1, resp2 = executor.submit(lambda: asyncio.run(execute_parallel())).result()

    # Keycloak behavior: At least one request succeeds (HTTP 200),
    # while the other either succeeds (near-simultaneous transaction window sharing reuse_id)
    # or is rejected with HTTP 400 invalid_grant. Neither must return HTTP 500.
    valid_statuses = {200, 400}
    assert resp1.status_code in valid_statuses, (
        f"Parallel refresh 1 unexpected status (RFC 6749 §5.2): {resp1.status_code}"
    )
    assert resp2.status_code in valid_statuses, (
        f"Parallel refresh 2 unexpected status (RFC 6749 §5.2): {resp2.status_code}"
    )
    assert 200 in (resp1.status_code, resp2.status_code), (
        "At least one concurrent refresh request must succeed (RFC 6749 §6)"
    )
    if resp1.status_code == 400:
        assert resp1.json().get("error") == "invalid_grant", (
            "Rejected parallel refresh must return invalid_grant (RFC 6749 §5.2)"
        )
    if resp2.status_code == 400:
        assert resp2.json().get("error") == "invalid_grant", (
            "Rejected parallel refresh must return invalid_grant (RFC 6749 §5.2)"
        )
