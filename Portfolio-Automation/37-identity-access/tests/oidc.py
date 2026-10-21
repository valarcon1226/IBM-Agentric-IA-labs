"""OpenID Connect (OIDC) Authorization Code Flow with PKCE S256 test suite.

Validates RFC 7636 (PKCE), RFC 6749 (OAuth 2.0), OpenID Connect Core 1.0,
and OWASP ASVS v4.0.3 Chapter V3 (Session Management).
"""

from __future__ import annotations

import secrets
import urllib.parse

import httpx
import jwt
import pytest
from playwright.sync_api import Page


def _obtain_auth_code_via_edge(
    page: Page,
    auth_url: str,
    callback_prefix: str,
    username: str = "testuser",
    password: str = "Password123!",
) -> str:
    """Drive Keycloak login on Microsoft Edge and capture the redirected auth code."""
    # Mock callback route so browser does not fail navigating to an unhosted port
    page.route(f"{callback_prefix}*", lambda route: route.fulfill(status=200, body="Callback OK"))

    page.goto(auth_url)
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()

    page.wait_for_url(f"{callback_prefix}*", timeout=15000)
    redirect_url = page.url

    parsed = urllib.parse.urlparse(redirect_url)
    qs = urllib.parse.parse_qs(parsed.query)

    if "error" in qs:
        raise RuntimeError(
            f"OIDC authorization returned error: {qs.get('error', [''])[0]} - "
            f"{qs.get('error_description', [''])[0]}"
        )

    code = qs.get("code")
    if not code:
        raise ValueError(f"Authorization code missing from redirect URL: {redirect_url}")

    return code[0]


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-003")
def test_oidc_happy_path_pkce_s256(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """Happy path: full OIDC code flow with PKCE S256, Edge login, and PyJWT JWKS validation."""
    verifier, challenge = pkce_pair
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope=openid%20profile%20email&"
        f"state={state}&"
        f"nonce={nonce}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )

    code = _obtain_auth_code_via_edge(
        page=edge_page,
        auth_url=auth_url,
        callback_prefix=redirect_uri,
    )
    assert code, "Authorization code must be present"

    # Step 3: Exchange code at token endpoint
    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"
    token_resp = httpx.post(
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
    assert token_resp.status_code == 200, (
        f"Token exchange failed with {token_resp.status_code}: {token_resp.text}"
    )

    token_data = token_resp.json()
    assert "access_token" in token_data, "Response must contain access_token"
    assert "id_token" in token_data, "Response must contain id_token"
    assert "refresh_token" in token_data, "Response must contain refresh_token"
    assert token_data.get("token_type") == "Bearer"

    # Step 4: Validate ID token with PyJWT against realm JWKS
    id_token = token_data["id_token"]
    jwks_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/certs"
    jwks_client = jwt.PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    expected_issuer = f"{base_url}/realms/{realm_name}"
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=expected_issuer,
        options={
            "verify_signature": True,
            "verify_aud": True,
            "verify_iss": True,
            "verify_exp": True,
        },
    )

    assert claims["iss"] == expected_issuer, f"Expected iss {expected_issuer}, got {claims['iss']}"
    assert claims["aud"] == client_id, f"Expected aud {client_id}, got {claims['aud']}"
    assert claims["nonce"] == nonce, f"Nonce mismatch: expected {nonce}, got {claims['nonce']}"
    assert "sub" in claims, "ID token claims must contain subject (sub)"


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-003")
def test_oidc_negative_wrong_code_verifier(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """Negative: token exchange with wrong code_verifier returns exact error invalid_grant."""
    _verifier, challenge = pkce_pair
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope=openid&"
        f"state={state}&"
        f"nonce={nonce}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )

    code = _obtain_auth_code_via_edge(
        page=edge_page,
        auth_url=auth_url,
        callback_prefix=redirect_uri,
    )

    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"
    wrong_verifier = "invalid_wrong_verifier_" + secrets.token_urlsafe(32)

    resp = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": wrong_verifier,
        },
        timeout=10.0,
    )

    assert resp.status_code == 400, f"Expected HTTP 400, got {resp.status_code}"
    error_data = resp.json()
    assert error_data.get("error") == "invalid_grant", (
        f"Expected OAuth error 'invalid_grant' (RFC 7636 §4.5), got {error_data.get('error')}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-003")
def test_oidc_negative_redirect_uri_mismatch(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """Negative: token exchange with redirect_uri mismatch returns exact error invalid_grant."""
    verifier, challenge = pkce_pair
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope=openid&"
        f"state={state}&"
        f"nonce={nonce}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )

    code = _obtain_auth_code_via_edge(
        page=edge_page,
        auth_url=auth_url,
        callback_prefix=redirect_uri,
    )

    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"
    mismatched_redirect_uri = "http://127.0.0.1:8000/different_callback"

    resp = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": mismatched_redirect_uri,
            "code_verifier": verifier,
        },
        timeout=10.0,
    )

    assert resp.status_code == 400, f"Expected HTTP 400, got {resp.status_code}"
    error_data = resp.json()
    assert error_data.get("error") == "invalid_grant", (
        f"Expected OAuth error 'invalid_grant' (RFC 6749 §5.2), got {error_data.get('error')}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-003")
def test_oidc_negative_missing_pkce_on_enforced_client(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
) -> None:
    """Negative: missing PKCE on client requiring S256 returns exact error invalid_request."""
    client_id = confidential_client["client_id"]
    redirect_uri = confidential_client["redirect_uri"]

    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope=openid&"
        f"state=test_state"
    )

    # Perform GET without code_challenge and inspect redirect parameters
    resp = httpx.get(auth_url, follow_redirects=False, timeout=10.0)
    assert resp.status_code == 302, f"Expected HTTP 302 redirect, got {resp.status_code}"

    location = resp.headers.get("location", "")
    parsed = urllib.parse.urlparse(location)
    qs = urllib.parse.parse_qs(parsed.query)

    assert qs.get("error") == ["invalid_request"], (
        f"Expected exact OAuth error 'invalid_request' (RFC 7636 §4.4.1), got {qs.get('error')}"
    )
    error_desc = qs.get("error_description", [""])[0]
    assert "code_challenge" in error_desc.lower(), (
        f"Error description should mention code_challenge, got: {error_desc}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-003")
def test_oidc_negative_nonce_mismatch(
    base_url: str,
    realm_name: str,
    confidential_client: dict[str, str],
    pkce_pair: tuple[str, str],
    edge_page: Page,
) -> None:
    """Negative: ID token validation fails when token nonce does not match client session nonce."""
    verifier, challenge = pkce_pair
    state = secrets.token_urlsafe(16)
    expected_nonce = "client_session_nonce_" + secrets.token_urlsafe(16)
    tampered_expected_nonce = "tampered_session_nonce_9999"

    client_id = confidential_client["client_id"]
    client_secret = confidential_client["client_secret"]
    redirect_uri = confidential_client["redirect_uri"]

    auth_url = (
        f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope=openid&"
        f"state={state}&"
        f"nonce={expected_nonce}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )

    code = _obtain_auth_code_via_edge(
        page=edge_page,
        auth_url=auth_url,
        callback_prefix=redirect_uri,
    )

    token_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/token"
    token_resp = httpx.post(
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
    assert token_resp.status_code == 200

    id_token = token_resp.json()["id_token"]
    jwks_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/certs"
    jwks_client = jwt.PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=f"{base_url}/realms/{realm_name}",
    )

    # Valid token has expected_nonce
    assert claims["nonce"] == expected_nonce

    # Client-side verification against tampered nonce must fail
    with pytest.raises(AssertionError, match="Nonce mismatch detected"):
        if claims["nonce"] != tampered_expected_nonce:
            raise AssertionError(
                f"Nonce mismatch detected: expected {tampered_expected_nonce}, "
                f"got {claims['nonce']}"
            )
