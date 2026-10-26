"""API tests for pagination in LiteLLM key listing and spend logs.

Verifies:
1. REQ-LLM-009: Pagination on /key/list:
   - Pinned parameters in LiteLLM main-v1.59.8 (key_management_endpoints.py:1646):
     * 'page' (int, ge=1, default=1): Page number.
     * 'size' (int, ge=1, le=100, default=10): Page size.
     * 'user_id' (str, optional): Filter keys by user ID.
     * Response schema: KeyListResponseObject (keys, total_count, current_page, total_pages).
     * Note: /key/list returns sha256 hashed tokens stored in DB table
       LiteLLM_VerificationToken.
   - Create 250 keys with dedicated user_id.
   - Walk paginated key list with page sizes 1, 13, and 100:
     Assert every key visited exactly once, zero duplicates, zero missing.
2. REQ-LLM-010: Pagination on /spend/logs/ui:
   - Pinned parameters in LiteLLM main-v1.59.8 (spend_management_endpoints.py:1655):
     * 'page' (int, ge=1, default=1): Page number.
     * 'page_size' (int, ge=1, le=100, default=50): Items per page.
     * 'start_date' (str, required format '%Y-%m-%d %H:%M:%S'): Start time window.
     * 'end_date' (str, required format '%Y-%m-%d %H:%M:%S'): End time window.
     * Response schema: {"data": List[dict], "total": int, "page": int, ...}.
   - Walk paginated spend logs over 500 requests with page sizes 1, 13, and 100:
     Assert every request_id visited exactly once, identical ordering, zero duplicates.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import math
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
import pytest

from tests.conftest import wait_until
from tests.fake_upstream import FakeUpstreamServer


@pytest.mark.api
def test_key_list_pagination_250_keys(
    litellm_base_url: str,
    litellm_master_key: str,
) -> None:
    """Create 250 keys, walk /key/list with page sizes 1, 13, 100, assert exactly once."""
    batch_id = uuid.uuid4().hex[:8]
    test_user_id = f"user-pag-{batch_id}"
    num_keys = 250

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json",
    }

    # 1. Create 250 keys concurrently using ThreadPoolExecutor for speed
    created_hashes: List[str] = []

    def _create_single_key(idx: int) -> str:
        payload = {
            "key_alias": f"pag-key-{batch_id}-{idx:03d}",
            "user_id": test_user_id,
            "models": ["fake-primary"],
        }
        with httpx.Client(base_url=litellm_base_url, timeout=15.0) as client:
            resp = client.post("/key/generate", headers=headers, json=payload)
            assert resp.status_code == 200, f"Key generation failed: {resp.text}"
            data = resp.json()
            raw_token = str(data["key"])
            # In LiteLLM v1.59.8, litellm_verificationtoken table stores sha256(token)
            # which is returned in /key/list keys array.
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            return token_hash

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_create_single_key, i) for i in range(num_keys)]
        for f in concurrent.futures.as_completed(futures):
            created_hashes.append(f.result())

    assert len(created_hashes) == num_keys
    expected_token_set = set(created_hashes)
    assert len(expected_token_set) == num_keys, "Created token hashes must all be distinct"

    # 2. Walk paginated key list with page sizes 1, 13, and 100
    # Citing LiteLLM v1.59.8 list_keys parameters:
    # 'page' (ge=1) and 'size' (ge=1, le=100)
    page_sizes = [1, 13, 100]

    with httpx.Client(base_url=litellm_base_url, timeout=30.0) as client:
        for page_size in page_sizes:
            expected_total_pages = math.ceil(num_keys / page_size)
            collected_tokens: List[str] = []

            for page in range(1, expected_total_pages + 1):
                resp = client.get(
                    f"/key/list?user_id={test_user_id}&page={page}&size={page_size}",
                    headers=headers,
                )
                assert resp.status_code == 200, (
                    f"Failed on page {page} size {page_size}: {resp.text}"
                )
                data = resp.json()

                # Validate pagination metadata
                assert data["total_count"] == num_keys
                assert data["current_page"] == page
                assert data["total_pages"] == expected_total_pages

                page_keys = data.get("keys", [])
                if page < expected_total_pages:
                    assert len(page_keys) == page_size
                else:
                    expected_last_page_size = num_keys - (expected_total_pages - 1) * page_size
                    assert len(page_keys) == expected_last_page_size

                collected_tokens.extend(page_keys)

            # Assert every key visited exactly once
            assert len(collected_tokens) == num_keys, (
                f"Page size {page_size}: expected {num_keys} keys, got {len(collected_tokens)}"
            )
            assert len(set(collected_tokens)) == num_keys, (
                f"Page size {page_size} produced duplicate keys"
            )
            assert set(collected_tokens) == expected_token_set, (
                f"Page size {page_size} keys do not match created keys"
            )


@pytest.mark.api
def test_spend_logs_pagination_500_requests(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    """Walk /spend/logs/ui over 500 requests with page sizes 1, 13, 100: assert identical 500."""
    target_count = 500
    headers = {"Authorization": f"Bearer {litellm_master_key}"}

    # Reset fake upstream to clean state
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)

    # 1. Create dedicated key to generate 500 spend logs via fake upstream
    key_resp = httpx.post(
        f"{litellm_base_url}/key/generate",
        headers=headers,
        json={
            "key_alias": f"pag-spend-{uuid.uuid4().hex[:8]}",
            "models": ["fake-primary"],
        },
        timeout=15.0,
    )
    assert key_resp.status_code == 200, f"Key generation failed: {key_resp.text}"
    test_key = key_resp.json()["key"]

    # Calculate date window relative to now (UTC)
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    def _get_spend_count() -> int:
        with httpx.Client(base_url=litellm_base_url, timeout=10.0) as client:
            resp = client.get(
                "/spend/logs/ui",
                headers=headers,
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "page": 1,
                    "page_size": 1,
                },
            )
            if resp.status_code == 200:
                return int(resp.json().get("total", 0))
        return 0

    initial_count = _get_spend_count()

    # 2. Concurrently generate 500 requests with paced delays to guarantee distinct timestamps
    def _send_spend_req(i: int) -> None:
        time.sleep(i * 0.005)
        with httpx.Client(base_url=litellm_base_url, timeout=15.0) as client:
            resp = client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {test_key}"},
                json={
                    "model": "fake-primary",
                    "messages": [{"role": "user", "content": f"Pagination ping {i}"}],
                },
            )
            assert resp.status_code == 200, f"Request {i} failed: {resp.text}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(_send_spend_req, range(target_count)))

    expected_total = initial_count + target_count

    # Citing LiteLLM v1.59.8 ui_view_spend_logs parameters:
    # 'page' (ge=1), 'page_size' (ge=1, le=100), 'start_date', 'end_date'
    with httpx.Client(base_url=litellm_base_url, timeout=30.0) as client:
        # Wait for LiteLLM background batcher to flush all 500 spend logs
        wait_until(
            lambda: _get_spend_count() >= expected_total,
            description=f"LiteLLM flush of all {target_count} spend logs",
            timeout=60.0,
            interval=0.5,
        )

        # Allow queue to settle
        time.sleep(1.0)

        # Check total available records in db
        probe = client.get(
            "/spend/logs/ui",
            headers=headers,
            params={
                "start_date": start_date,
                "end_date": end_date,
                "page": 1,
                "page_size": 1,
            },
        )
        assert probe.status_code == 200, f"Probe failed: {probe.text}"
        total_in_db = probe.json().get("total", 0)
        assert total_in_db >= target_count, (
            f"Database must contain at least {target_count} spend logs, found {total_in_db}"
        )

        # Baseline: fetch 500 records using page_size=100 (5 pages)
        baseline_request_ids: List[str] = []
        for page in range(1, (target_count // 100) + 1):
            r = client.get(
                "/spend/logs/ui",
                headers=headers,
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "page": page,
                    "page_size": 100,
                },
            )
            assert r.status_code == 200
            page_data = r.json().get("data", [])
            for item in page_data:
                baseline_request_ids.append(item["request_id"])

        assert len(baseline_request_ids) == target_count
        assert len(set(baseline_request_ids)) == target_count, "Spend logs baseline has duplicates"

        # Walk with page_size = 13 (39 pages: 38 of 13 = 494 + 6 from page 39 = 500)
        p13_ids: List[str] = []
        p13_total_pages = math.ceil(target_count / 13)
        for page in range(1, p13_total_pages + 1):
            r = client.get(
                "/spend/logs/ui",
                headers=headers,
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "page": page,
                    "page_size": 13,
                },
            )
            assert r.status_code == 200
            for item in r.json().get("data", []):
                p13_ids.append(item["request_id"])
                if len(p13_ids) == target_count:
                    break

        assert p13_ids == baseline_request_ids, (
            "Page size 13 produced different spend logs sequence"
        )

        # Walk with page_size = 1 (500 pages)
        p1_ids: List[str] = []
        for page in range(1, target_count + 1):
            r = client.get(
                "/spend/logs/ui",
                headers=headers,
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "page": page,
                    "page_size": 1,
                },
            )
            assert r.status_code == 200
            data = r.json().get("data", [])
            assert len(data) == 1
            p1_ids.append(data[0]["request_id"])

        assert p1_ids == baseline_request_ids, (
            "Page size 1 produced different spend logs sequence"
        )
