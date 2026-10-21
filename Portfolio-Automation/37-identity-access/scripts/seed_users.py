"""Seed 10,000 users into Keycloak realm via the admin API in batches."""

from __future__ import annotations

import os

import httpx


def get_admin_token(base_url: str, admin_user: str, admin_pass: str) -> str:
    url = f"{base_url}/realms/master/protocol/openid-connect/token"
    data = {
        "client_id": "admin-cli",
        "grant_type": "password",
        "username": admin_user,
        "password": admin_pass,
    }
    resp = httpx.post(url, data=data, timeout=30.0)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"Failed to obtain admin token from {url}")
    return str(token)


def get_user_count(base_url: str, realm: str, token: str) -> int:
    url = f"{base_url}/admin/realms/{realm}/users/count"
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(url, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return int(resp.text.strip())


def build_user(idx: int) -> dict[str, object]:
    """Build a deterministic user payload for index idx (0..9999)."""
    if idx == 0:
        username = "testuser"
        first_name = "Test"
        last_name = "User"
    elif idx <= 1200:
        username = f"bench_user_{idx:05d}"
        first_name = "Benchmark"
        last_name = f"User {idx:05d}"
    else:
        username = f"user_{idx:05d}"
        first_name = "Standard"
        last_name = f"User {idx:05d}"

    return {
        "username": username,
        "enabled": True,
        "email": f"{username}@example.com",
        "firstName": first_name,
        "lastName": last_name,
        "emailVerified": True,
        "credentials": [
            {
                "type": "password",
                "value": "Password123!",
                "temporary": False,
            }
        ],
    }


def seed_users(
    target_count: int = 10000,
    batch_size: int = 1000,
) -> int:
    base_url = os.getenv("KEYCLOAK_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
    admin_user = os.getenv("KEYCLOAK_ADMIN", "admin")
    admin_pass = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
    realm = os.getenv("KEYCLOAK_REALM", "identity-realm")

    token = get_admin_token(base_url, admin_user, admin_pass)
    current_count = get_user_count(base_url, realm, token)

    if current_count >= target_count:
        print(f"Current user count is already {current_count}")
        return current_count

    print(f"Current user count: {current_count}. Seeding {target_count - current_count} users...")

    import_url = f"{base_url}/admin/realms/{realm}/partialImport"

    for start_idx in range(current_count, target_count, batch_size):
        end_idx = min(start_idx + batch_size, target_count)
        users = [build_user(i) for i in range(start_idx, end_idx)]

        payload = {
            "ifResourceExists": "SKIP",
            "users": users,
        }

        # Keep admin token fresh
        token = get_admin_token(base_url, admin_user, admin_pass)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        resp = httpx.post(import_url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
        batch_res = resp.json()
        added = batch_res.get("added", 0)
        skipped = batch_res.get("skipped", 0)
        print(f"Batch {start_idx}..{end_idx}: added={added}, skipped={skipped}")

    token = get_admin_token(base_url, admin_user, admin_pass)
    final_count = get_user_count(base_url, realm, token)
    return final_count


if __name__ == "__main__":
    count = seed_users()
    print(count)
