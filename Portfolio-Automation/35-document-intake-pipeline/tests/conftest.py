"""Shared pytest fixtures for Paperless-ngx document intake pipeline test suite."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("PAPERLESS_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def toxiproxy_url() -> str:
    return os.getenv("TOXIPROXY_URL", "http://127.0.0.1:8474").rstrip("/")


@pytest.fixture(scope="session")
def admin_credentials() -> tuple[str, str]:
    return (
        os.getenv("PAPERLESS_ADMIN_USER", "admin"),
        os.getenv("PAPERLESS_ADMIN_PASSWORD", "admin"),
    )


@pytest.fixture(scope="session")
def api_token(base_url: str, admin_credentials: tuple[str, str]) -> str:
    # Check .token file first
    token_path = Path(__file__).resolve().parent.parent / ".token"
    if token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token

    token_env = os.getenv("PAPERLESS_API_TOKEN")
    if token_env:
        return token_env.strip()

    # Obtain via /api/token/
    username, password = admin_credentials
    resp = httpx.post(
        f"{base_url}/api/token/",
        json={"username": username, "password": password},
        timeout=10.0,
    )
    resp.raise_for_status()
    token = str(resp.json()["token"]).strip()
    token_path.write_text(token, encoding="utf-8")
    return token


@pytest.fixture(scope="session")
def auth_headers(api_token: str) -> dict[str, str]:
    return {"Authorization": f"Token {api_token}"}


@pytest.fixture(scope="session")
def corpus_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "corpus" / "generated"


@pytest.fixture(scope="session")
def labels_file() -> Path:
    return Path(__file__).resolve().parent.parent / "corpus" / "labels.csv"
