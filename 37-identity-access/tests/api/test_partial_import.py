"""Tests for Keycloak partialImport endpoint and collision policies.

Validates:
- OWASP ASVS v4.0.3 Chapter V13 (API and Web Service Verification) / REQ-IAM-007.
- Itemized results (added, skipped, overwritten) for 1,000 users with 50 pre-existing conflicts.
- Collision policies: SKIP, OVERWRITE, and FAIL, executed against fresh realms.
- Read-back verification of database state through Keycloak REST API.
- Atomicity verification of FAIL policy (all-or-nothing transactional rollback).
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest


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


def _create_fresh_realm(base_url: str, realm_name: str, token: str) -> None:
    resp = httpx.post(
        f"{base_url}/admin/realms",
        json={"realm": realm_name, "enabled": True},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    if resp.status_code != 201:
        raise RuntimeError(f"Failed to create realm {realm_name}: {resp.status_code} {resp.text}")


def _delete_realm(base_url: str, realm_name: str, token: str) -> None:
    httpx.delete(
        f"{base_url}/admin/realms/{realm_name}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )


def _get_user_count(base_url: str, realm_name: str, token: str) -> int:
    resp = httpx.get(
        f"{base_url}/admin/realms/{realm_name}/users/count",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return int(resp.text.strip())


def _build_payloads() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate 50 baseline conflicting users and 1,000 import users (50 conflicts + 950 new)."""
    existing_users: list[dict[str, Any]] = [
        {
            "username": f"import_user_conflict_{i:04d}",
            "email": f"conflict_{i:04d}@example.com",
            "firstName": "Baseline",
            "lastName": f"User_{i:04d}",
            "enabled": True,
        }
        for i in range(50)
    ]

    # Structure 1,000 users: 100 new, then 50 conflicts (with updated attrs), then 850 new
    leading_new: list[dict[str, Any]] = [
        {
            "username": f"import_user_new_{i:04d}",
            "email": f"new_{i:04d}@example.com",
            "firstName": "BrandNew",
            "lastName": f"Lead_{i:04d}",
            "enabled": True,
        }
        for i in range(100)
    ]

    conflicting_updated: list[dict[str, Any]] = [
        {
            "username": f"import_user_conflict_{i:04d}",
            "email": f"conflict_{i:04d}@example.com",
            "firstName": "UpdatedAttribute",
            "lastName": f"Overwritten_{i:04d}",
            "enabled": True,
        }
        for i in range(50)
    ]

    trailing_new: list[dict[str, Any]] = [
        {
            "username": f"import_user_new_{i:04d}",
            "email": f"new_{i:04d}@example.com",
            "firstName": "BrandNew",
            "lastName": f"Trail_{i:04d}",
            "enabled": True,
        }
        for i in range(100, 950)
    ]

    import_1000 = leading_new + conflicting_updated + trailing_new
    assert len(import_1000) == 1000, f"Expected 1,000 users, built {len(import_1000)}"
    assert len(existing_users) == 50, f"Expected 50 baseline users, built {len(existing_users)}"

    return existing_users, import_1000


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-007")
def test_partial_import_skip_policy(base_url: str) -> None:
    """Verify SKIP policy: 950 added, 50 skipped, baseline attributes preserved."""
    token = _get_admin_token(base_url)
    realm_name = f"realm-import-skip-{int(time.time())}"
    _create_fresh_realm(base_url, realm_name, token)

    try:
        existing_50, import_1000 = _build_payloads()

        # Seed baseline 50 users
        seed_resp = httpx.post(
            f"{base_url}/admin/realms/{realm_name}/partialImport",
            json={"ifResourceExists": "FAIL", "users": existing_50},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert seed_resp.status_code == 200, f"Seed failed: {seed_resp.text}"
        assert _get_user_count(base_url, realm_name, token) == 50

        # Run partial import with SKIP policy
        import_resp = httpx.post(
            f"{base_url}/admin/realms/{realm_name}/partialImport",
            json={"ifResourceExists": "SKIP", "users": import_1000},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        assert import_resp.status_code == 200, f"Import failed: {import_resp.text}"
        data = import_resp.json()

        # Assert reported itemized counts
        assert data.get("added") == 950, f"Expected 950 added, got {data.get('added')}"
        assert data.get("skipped") == 50, f"Expected 50 skipped, got {data.get('skipped')}"
        assert data.get("overwritten") == 0, (
            f"Expected 0 overwritten, got {data.get('overwritten')}"
        )

        results: list[dict[str, Any]] = data.get("results", [])
        assert len(results) == 1000
        added_results = [r for r in results if r.get("action") == "ADDED"]
        skipped_results = [r for r in results if r.get("action") == "SKIPPED"]
        assert len(added_results) == 950
        assert len(skipped_results) == 50

        # Assert database state through API
        final_count = _get_user_count(base_url, realm_name, token)
        assert final_count == 1000, f"Expected 1,000 total users, got {final_count}"

        # Assert baseline users were NOT overwritten
        check_user = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users?username=import_user_conflict_0000",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        ).json()[0]
        assert check_user["firstName"] == "Baseline", (
            f"Expected 'Baseline' under SKIP, found '{check_user['firstName']}'"
        )
    finally:
        _delete_realm(base_url, realm_name, token)


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-007")
def test_partial_import_overwrite_policy(base_url: str) -> None:
    """Verify OVERWRITE policy: 950 added, 50 overwritten, baseline attributes updated."""
    token = _get_admin_token(base_url)
    realm_name = f"realm-import-over-{int(time.time())}"
    _create_fresh_realm(base_url, realm_name, token)

    try:
        existing_50, import_1000 = _build_payloads()

        # Seed baseline 50 users
        seed_resp = httpx.post(
            f"{base_url}/admin/realms/{realm_name}/partialImport",
            json={"ifResourceExists": "FAIL", "users": existing_50},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert seed_resp.status_code == 200, f"Seed failed: {seed_resp.text}"
        assert _get_user_count(base_url, realm_name, token) == 50

        # Run partial import with OVERWRITE policy
        import_resp = httpx.post(
            f"{base_url}/admin/realms/{realm_name}/partialImport",
            json={"ifResourceExists": "OVERWRITE", "users": import_1000},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        assert import_resp.status_code == 200, f"Import failed: {import_resp.text}"
        data = import_resp.json()

        # Assert reported itemized counts
        assert data.get("added") == 950, f"Expected 950 added, got {data.get('added')}"
        assert data.get("skipped") == 0, f"Expected 0 skipped, got {data.get('skipped')}"
        assert data.get("overwritten") == 50, (
            f"Expected 50 overwritten, got {data.get('overwritten')}"
        )

        results: list[dict[str, Any]] = data.get("results", [])
        assert len(results) == 1000
        added_results = [r for r in results if r.get("action") == "ADDED"]
        overwritten_results = [r for r in results if r.get("action") == "OVERWRITTEN"]
        assert len(added_results) == 950
        assert len(overwritten_results) == 50

        # Assert database state through API
        final_count = _get_user_count(base_url, realm_name, token)
        assert final_count == 1000, f"Expected 1,000 total users, got {final_count}"

        # Assert baseline users WERE overwritten
        check_user = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users?username=import_user_conflict_0000",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        ).json()[0]
        assert check_user["firstName"] == "UpdatedAttribute", (
            f"Expected 'UpdatedAttribute' under OVERWRITE, found '{check_user['firstName']}'"
        )
    finally:
        _delete_realm(base_url, realm_name, token)


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-007")
def test_partial_import_fail_policy(base_url: str) -> None:
    """Verify FAIL policy: returns 409 Conflict and rolls back all-or-nothing atomically."""
    token = _get_admin_token(base_url)
    realm_name = f"realm-import-fail-{int(time.time())}"
    _create_fresh_realm(base_url, realm_name, token)

    try:
        existing_50, import_1000 = _build_payloads()

        # Seed baseline 50 users
        seed_resp = httpx.post(
            f"{base_url}/admin/realms/{realm_name}/partialImport",
            json={"ifResourceExists": "FAIL", "users": existing_50},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert seed_resp.status_code == 200, f"Seed failed: {seed_resp.text}"
        assert _get_user_count(base_url, realm_name, token) == 50

        # Run partial import with FAIL policy
        import_resp = httpx.post(
            f"{base_url}/admin/realms/{realm_name}/partialImport",
            json={"ifResourceExists": "FAIL", "users": import_1000},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

        # Assert HTTP status and error details
        assert import_resp.status_code == 409, (
            f"Expected 409 Conflict under FAIL policy, got {import_resp.status_code}"
        )
        error_body = import_resp.json()
        error_message = error_body.get("errorMessage", "")
        assert "already exists" in error_message, (
            f"Expected 'already exists' in error message, got: {error_message}"
        )

        # Assert database state: all-or-nothing transactional rollback
        # 100 new users preceded the conflict in the payload; none must be present
        final_count = _get_user_count(base_url, realm_name, token)
        assert final_count == 50, (
            f"Atomicity violation! Expected 50 baseline users after FAIL, found {final_count}"
        )

        # Confirm leading new user was not inserted
        lead_probe = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users?username=import_user_new_0000",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        ).json()
        assert len(lead_probe) == 0, (
            f"Atomicity violation! Leading user before conflict was committed to DB: {lead_probe}"
        )

        # Confirm baseline user was not modified
        conflict_probe = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users?username=import_user_conflict_0000",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        ).json()[0]
        assert conflict_probe["firstName"] == "Baseline", (
            f"Baseline user was corrupted during failed import: {conflict_probe}"
        )
    finally:
        _delete_realm(base_url, realm_name, token)
