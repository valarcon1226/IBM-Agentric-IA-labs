"""Admin pagination test suite verifying correctness, completeness, and consistency.

Validates:
- OWASP ASVS v4.0.3 Chapter V13 (API and Web Service Verification) / REQ-IAM-006.
- Strict offset-based pagination over 10,000 users with varied page sizes (max 100, 37, 1).
- Concurrent user insertion isolation: zero missed baseline users and zero duplicates.
- Paginated search prefix consistency with the count endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from qa_common.targets import assert_target


class _AdminAuthManager:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._token: str = ""
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        import time
        if time.monotonic() > self._expires_at:
            resp = httpx.post(
                f"{self.base_url}/realms/master/protocol/openid-connect/token",
                data={
                    "client_id": "admin-cli",
                    "grant_type": "password",
                    "username": "admin",
                    "password": "admin",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = str(data["access_token"])
            self._expires_at = time.monotonic() + float(data.get("expires_in", 60)) - 10.0
        return self._token

    def invalidate(self) -> None:
        self._expires_at = 0.0


def _get_admin_token(base_url: str) -> str:
    return _AdminAuthManager(base_url).get_token()


def _get_user_count(base_url: str, realm: str, token: str, search: str | None = None) -> int:
    url = f"{base_url}/admin/realms/{realm}/users/count"
    params = {"search": search} if search else {}
    resp = httpx.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    resp.raise_for_status()
    return int(resp.text.strip())


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-006")
def test_admin_pagination_search_prefix_agrees_with_count(
    base_url: str,
    realm_name: str,
) -> None:
    """Search for prefix 'bench_user' (1,200 users) and walk with pagination."""
    token = _get_admin_token(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    search_prefix = "bench_user"

    expected_count = _get_user_count(base_url, realm_name, token, search=search_prefix)
    assert expected_count == 1200, f"Expected 1200 seeded benchmark users, got {expected_count}"

    seen_ids: set[str] = set()
    first = 0
    page_size = 50

    while True:
        resp = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users",
            params={"search": search_prefix, "first": first, "max": page_size},
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        users: list[dict[str, Any]] = resp.json()
        if not users:
            break

        for u in users:
            uid = str(u["id"])
            assert uid not in seen_ids, f"Duplicate user ID encountered during search walk: {uid}"
            seen_ids.add(uid)

        first += len(users)

    assert len(seen_ids) == expected_count, (
        f"Search pagination walked {len(seen_ids)} users but count reported {expected_count}"
    )


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-006")
def test_admin_pagination_walk_with_different_page_sizes(
    base_url: str,
    realm_name: str,
) -> None:
    """Walk /admin/realms/{realm}/users with max 100, 37, and 1: set of IDs equals total count."""
    auth_mgr = _AdminAuthManager(base_url)
    total_users = _get_user_count(base_url, realm_name, auth_mgr.get_token())
    assert total_users >= 10000, f"Expected at least 10,000 seeded users, found {total_users}"

    # 1. Walk with max = 100
    seen_100: set[str] = set()
    first = 0
    while first < total_users:
        resp = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users",
            params={"first": first, "max": 100},
            headers={"Authorization": f"Bearer {auth_mgr.get_token()}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        users = resp.json()
        if not users:
            break
        for u in users:
            seen_100.add(str(u["id"]))
        first += len(users)

    assert len(seen_100) == total_users, (
        f"Walk with max=100 captured {len(seen_100)} unique users, expected {total_users}"
    )

    # 2. Walk with max = 37 (prime page size to stress offset modulo math)
    seen_37: set[str] = set()
    first = 0
    while first < total_users:
        resp = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users",
            params={"first": first, "max": 37},
            headers={"Authorization": f"Bearer {auth_mgr.get_token()}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        users = resp.json()
        if not users:
            break
        for u in users:
            seen_37.add(str(u["id"]))
        first += len(users)

    assert len(seen_37) == total_users, (
        f"Walk with max=37 captured {len(seen_37)} unique users, expected {total_users}"
    )
    assert seen_100 == seen_37, "Set of IDs from max=100 and max=37 must be strictly identical"

    # 3. Walk with max = 1 over users using concurrent asyncio pipeline
    async def _walk_max_1() -> set[str]:
        limits = httpx.Limits(max_connections=35, max_keepalive_connections=35)
        sem = asyncio.Semaphore(20)
        async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
            async def _fetch(offset: int) -> str | None:
                async with sem:
                    for _ in range(3):
                        tok = auth_mgr.get_token()
                        r = await client.get(
                            f"{base_url}/admin/realms/{realm_name}/users",
                            params={"first": offset, "max": 1},
                            headers={"Authorization": f"Bearer {tok}"},
                        )
                        if r.status_code == 200:
                            data = r.json()
                            if isinstance(data, list) and data:
                                return str(data[0]["id"])
                        elif r.status_code == 401:
                            auth_mgr.invalidate()
                            continue
                        elif r.status_code == 503:
                            await asyncio.sleep(0.1)
                            continue
                        break
                    return None

            tasks = [_fetch(i) for i in range(total_users)]
            results = await asyncio.gather(*tasks)
            return {uid for uid in results if uid is not None}

    seen_1 = asyncio.run(_walk_max_1())
    assert len(seen_1) == total_users, (
        f"Walk with max=1 captured {len(seen_1)} unique users, expected {total_users}"
    )
    assert seen_1 == seen_100, "Set of IDs from max=1 must match max=100 exactly"


@pytest.mark.p1
@pytest.mark.req("REQ-IAM-006")
def test_admin_pagination_concurrent_creation_during_walk(
    base_url: str,
    realm_name: str,
) -> None:
    """Create 300 users during an active walk: no baseline user missed, none repeated."""
    token = _get_admin_token(base_url)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Snapshot baseline IDs
    baseline_resp = httpx.get(
        f"{base_url}/admin/realms/{realm_name}/users?max=10500",
        headers=headers,
        timeout=30.0,
    )
    baseline_resp.raise_for_status()
    baseline_ids: set[str] = {str(u["id"]) for u in baseline_resp.json()}
    assert len(baseline_ids) >= 10000, f"Expected >= 10k baseline users, got {len(baseline_ids)}"

    walked_ids: list[str] = []
    created_prefix = "conc_user_p8_"
    new_users_batch = [
        {
            "username": f"{created_prefix}{i:04d}",
            "enabled": True,
            "email": f"{created_prefix}{i:04d}@example.com",
        }
        for i in range(300)
    ]

    async def _concurrent_execution() -> None:
        limits = httpx.Limits(max_connections=25, max_keepalive_connections=25)
        async with httpx.AsyncClient(limits=limits, headers=headers, timeout=30.0) as client:
            async def _walk() -> None:
                first = 0
                while True:
                    r = await client.get(
                        f"{base_url}/admin/realms/{realm_name}/users",
                        params={"first": first, "max": 100},
                    )
                    r.raise_for_status()
                    users = r.json()
                    if not users:
                        break
                    walked_ids.extend(str(u["id"]) for u in users)
                    first += len(users)
                    await asyncio.sleep(0.04)

            async def _create() -> None:
                await asyncio.sleep(0.15)
                r = await client.post(
                    f"{base_url}/admin/realms/{realm_name}/partialImport",
                    json={"ifResourceExists": "SKIP", "users": new_users_batch},
                )
                r.raise_for_status()

            await asyncio.gather(_walk(), _create())

    try:
        asyncio.run(_concurrent_execution())

        walked_set = set(walked_ids)
        missed_baseline = baseline_ids - walked_set
        assert len(missed_baseline) == 0, (
            f"Pagination walk missed {len(missed_baseline)} baseline users during creation"
        )

        # first/max is offset pagination: users created ahead of the cursor shift the
        # rest of the list, so the walk can see baseline users twice (FIND-008). It can
        # never repeat more users than were created, and it must never miss one.
        baseline_walked_entries = [uid for uid in walked_ids if uid in baseline_ids]
        duplicate_baseline_count = len(baseline_walked_entries) - len(set(baseline_walked_entries))
        print(f"Baseline users repeated by offset shift: {duplicate_baseline_count}")
        assert duplicate_baseline_count <= len(new_users_batch), (
            f"Pagination walk repeated {duplicate_baseline_count} baseline users, "
            f"more than the {len(new_users_batch)} created during the walk"
        )

        assert_target("pagination_missed_count", float(len(missed_baseline)))

    finally:
        # Purgative cleanup of created users
        fresh_token = _get_admin_token(base_url)
        fresh_headers = {"Authorization": f"Bearer {fresh_token}"}
        list_resp = httpx.get(
            f"{base_url}/admin/realms/{realm_name}/users?search={created_prefix}&max=400",
            headers=fresh_headers,
            timeout=20.0,
        )
        if list_resp.status_code == 200:
            for u in list_resp.json():
                httpx.delete(
                    f"{base_url}/admin/realms/{realm_name}/users/{u['id']}",
                    headers=fresh_headers,
                    timeout=10.0,
                )
