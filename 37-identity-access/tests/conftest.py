"""Shared pytest fixtures for Keycloak IAM test suite."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("KEYCLOAK_BASE_URL", "http://127.0.0.1:8081").rstrip("/")


@pytest.fixture(scope="session")
def realm_name() -> str:
    return os.getenv("KEYCLOAK_REALM", "identity-realm")


@pytest.fixture(scope="session")
def admin_credentials() -> tuple[str, str]:
    return (
        os.getenv("KEYCLOAK_ADMIN", "admin"),
        os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"),
    )


@pytest.fixture(scope="session")
def confidential_client() -> dict[str, str]:
    return {
        "client_id": "confidential-web-app",
        "client_secret": os.getenv("CONFIDENTIAL_CLIENT_SECRET", "confidential-secret-1234"),
        "redirect_uri": "http://127.0.0.1:8000/callback",
    }


@pytest.fixture(scope="session")
def public_client() -> dict[str, str]:
    return {
        "client_id": "public-spa-app",
        "redirect_uri": "http://127.0.0.1:3000/callback",
    }


@pytest.fixture(scope="session")
def service_account_client() -> dict[str, str]:
    return {
        "client_id": "service-account-client",
        "client_secret": os.getenv("SERVICE_ACCOUNT_SECRET", "service-account-secret-1234"),
    }


@pytest.fixture
def pkce_pair() -> tuple[str, str]:
    """Generate high-entropy PKCE code_verifier and S256 code_challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@pytest.fixture
def edge_page(playwright: Playwright) -> Generator[Page, None, None]:
    """Launch Microsoft Edge in headless mode."""
    browser: Browser = playwright.chromium.launch(
        channel="msedge",
        headless=True,
    )
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    yield page
    context.close()
    browser.close()
