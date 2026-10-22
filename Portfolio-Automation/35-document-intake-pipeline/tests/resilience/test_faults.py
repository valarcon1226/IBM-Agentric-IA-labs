"""Resilience fault tests: Redis restart, Toxiproxy network severed, and client retry idempotency.

Tests 3 production fault scenarios:
- Test A: Start a 100-document burst, and when 30 tasks are done restart Redis.
- Test B: Start a 100-document burst and inject a 30s Toxiproxy timeout toxic on Redis.
- Test C: Upload one file, simulate a client retry by uploading the same bytes again,
  and assert that there is exactly 1 document with that checksum.

For A and B:
- Every task reaches a final state (SUCCESS or FAILURE).
- Number of documents equals expected ingests (100).
- No task stays PENDING or STARTED (tasks_stuck_after_fault == 0).
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import time
from typing import Any

import httpx
import pytest
from qa_common.targets import assert_target
from qa_common.toxiproxy import ToxiproxyClient

from corpus.generate import create_pdf_bytes


def _generate_synthetic_batch(count: int, tag: str) -> tuple[str, list[tuple[str, bytes]]]:
    """Generate in-memory valid synthetic PDFs with unique run tag and tokens."""
    batch = []
    run_tag = f"fault_{tag}_{int(time.time())}"
    base_ns = time.time_ns()
    for i in range(count):
        fname = f"{run_tag}_{i+1:04d}.pdf"
        token = f"TOKEN-{run_tag.upper()}-{i+1:04d}-{base_ns}"
        b = create_pdf_bytes(
            doc_id=2000 + i,
            doc_type="invoice",
            correspondent="Acme Corp",
            date_str="2026-04-15",
            amount_str="$750.00",
            iban="DE89 3704 0044 0532 7788 99",
            unique_token=token,
        )
        batch.append((fname, b))
    return run_tag, batch


async def _upload_pdf_batch(
    client: httpx.AsyncClient,
    upload_url: str,
    headers: dict[str, str],
    batch: list[tuple[str, bytes]],
    concurrency: int = 25,
) -> dict[str, str]:
    """Upload a batch of (filename, bytes) concurrently and return mapping of task_id -> filename."""
    semaphore = asyncio.Semaphore(concurrency)
    task_id_to_file: dict[str, str] = {}

    async def _post_one(filename: str, file_bytes: bytes) -> None:
        async with semaphore:
            resp = await client.post(
                upload_url,
                headers=headers,
                files={"document": (filename, file_bytes, "application/pdf")},
                timeout=60.0,
            )
            assert resp.status_code == 200, f"Upload error {filename}: {resp.status_code} - {resp.text}"
            tid = resp.json().strip()
            task_id_to_file[tid] = filename

    tasks = [_post_one(fname, b) for fname, b in batch]
    await asyncio.gather(*tasks)
    return task_id_to_file


async def _wait_for_tasks_drained(
    client: httpx.AsyncClient,
    tasks_url: str,
    headers: dict[str, str],
    target_task_ids: set[str],
    timeout_s: float = 600.0,
) -> dict[str, dict[str, Any]]:
    """Poll until all target task IDs reach terminal states (SUCCESS or FAILURE)."""
    deadline = time.time() + timeout_s
    final_tasks: dict[str, dict[str, Any]] = {}

    while time.time() < deadline:
        try:
            resp = await client.get(tasks_url, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                for t in resp.json():
                    tid = t.get("task_id")
                    if tid in target_task_ids and t.get("status") in ("SUCCESS", "FAILURE"):
                        final_tasks[tid] = t

            if len(final_tasks) == len(target_task_ids):
                return final_tasks
        except (httpx.HTTPError, OSError):
            pass
        await asyncio.sleep(2.0)

    raise TimeoutError(
        f"Tasks did not drain in {timeout_s}s. Completed: {len(final_tasks)}/{len(target_task_ids)}"
    )


async def _get_document_count(client: httpx.AsyncClient, base_url: str, headers: dict[str, str]) -> int:
    resp = await client.get(f"{base_url}/api/documents/", headers=headers, timeout=15.0)
    assert resp.status_code == 200
    return int(resp.json()["count"])


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-002")
@pytest.mark.xfail(
    strict=True,
    raises=TimeoutError,
    reason="FINDING-003: Kombu Redis unacked tasks not restored upon broker restart until 3600s visibility timeout",
)
@pytest.mark.asyncio
async def test_fault_redis_restart(
    base_url: str,
    auth_headers: dict[str, str],
) -> None:
    """Test A: Start a 100-document burst, and when 30 tasks are done run docker restart redis.

    Assert:
    - Every task reaches a final state (SUCCESS or FAILURE)
    - Number of documents equals expected ingests (100)
    - Zero tasks remain stuck in PENDING or STARTED
    """
    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"
    expected_count = 100
    run_tag, batch = _generate_synthetic_batch(expected_count, tag="restart")

    limits = httpx.Limits(max_connections=30, max_keepalive_connections=25)
    async with httpx.AsyncClient(limits=limits) as client:
        # Step 1: Upload 100 documents concurrently
        task_id_to_file = await _upload_pdf_batch(client, upload_url, auth_headers, batch, concurrency=25)
        target_ids = set(task_id_to_file.keys())
        assert len(target_ids) == expected_count

        # Step 2: Poll until at least 30 tasks finish
        completed_early: set[str] = set()
        while len(completed_early) < 30:
            try:
                resp = await client.get(tasks_url, headers=auth_headers, timeout=10.0)
                if resp.status_code == 200:
                    for t in resp.json():
                        if t.get("task_id") in target_ids and t.get("status") in ("SUCCESS", "FAILURE"):
                            completed_early.add(t["task_id"])
            except (httpx.HTTPError, OSError):
                pass
            await asyncio.sleep(1.0)

        # Step 3: Fault injection - restart Redis container
        await asyncio.to_thread(
            subprocess.run,
            ["docker", "compose", "restart", "redis"],
            check=True,
            capture_output=True,
        )

        # Step 4: Wait for all remaining tasks to drain
        final_tasks = await _wait_for_tasks_drained(client, tasks_url, auth_headers, target_ids, timeout_s=150.0)

        # Step 5: Assertions
        assert len(final_tasks) == expected_count
        statuses = {t["status"] for t in final_tasks.values()}
        assert "PENDING" not in statuses, "Tasks remained stuck in PENDING after Redis restart"
        assert "STARTED" not in statuses, "Tasks remained stuck in STARTED after Redis restart"

        # Assert document count for batch equals expected ingests
        restart_resp = await client.get(
            f"{base_url}/api/documents/?title__icontains={run_tag}&page_size=1",
            headers=auth_headers,
            timeout=15.0,
        )
        assert restart_resp.status_code == 200
        restart_count = restart_resp.json().get("count", 0)
        assert restart_count == expected_count, (
            f"Expected {expected_count} documents for batch '{run_tag}', got {restart_count}"
        )

        assert_target("tasks_stuck_after_fault", 0)


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-002")
@pytest.mark.asyncio
async def test_fault_toxiproxy_timeout_toxic(
    base_url: str,
    auth_headers: dict[str, str],
    toxiproxy_url: str,
) -> None:
    """Test B: Start a 100-document burst and add a Toxiproxy timeout toxic on Redis for 30 s.

    Assert:
    - Every task reaches a final state (SUCCESS or FAILURE)
    - Number of documents equals expected ingests (100)
    - Zero tasks remain stuck in PENDING or STARTED
    """
    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"
    expected_count = 100
    run_tag, batch = _generate_synthetic_batch(expected_count, tag="toxic")
    toxi = ToxiproxyClient(base_url=toxiproxy_url)

    # Clean up any leftover toxics on redis proxy before test
    current_toxics = [t.get("name") for t in toxi.get_proxy("redis").get("toxics", [])]
    if "redis_fault_timeout" in current_toxics:
        toxi.remove_toxic("redis", "redis_fault_timeout")

    limits = httpx.Limits(max_connections=30, max_keepalive_connections=25)
    async with httpx.AsyncClient(limits=limits) as client:
        # Step 1: Upload 100 documents concurrently
        task_id_to_file = await _upload_pdf_batch(client, upload_url, auth_headers, batch, concurrency=25)
        target_ids = set(task_id_to_file.keys())
        assert len(target_ids) == expected_count

        # Step 2: Inject Toxiproxy timeout toxic on Redis for 30s
        toxi.add_toxic(
            proxy_name="redis",
            toxic_name="redis_fault_timeout",
            toxic_type="timeout",
            attributes={"timeout": 30000},
        )
        try:
            # Hold fault for 30 seconds
            await asyncio.sleep(30.0)
        finally:
            # Remove toxic so Redis traffic resumes
            active_toxics = [t.get("name") for t in toxi.get_proxy("redis").get("toxics", [])]
            if "redis_fault_timeout" in active_toxics:
                toxi.remove_toxic("redis", "redis_fault_timeout")

        # Step 3: Wait for all 100 tasks to drain to final state
        final_tasks = await _wait_for_tasks_drained(client, tasks_url, auth_headers, target_ids, timeout_s=400.0)

        # Step 4: Assertions
        assert len(final_tasks) == expected_count
        statuses = {t["status"] for t in final_tasks.values()}
        assert "PENDING" not in statuses, "Tasks remained stuck in PENDING after Toxiproxy timeout"
        assert "STARTED" not in statuses, "Tasks remained stuck in STARTED after Toxiproxy timeout"

        success_count = sum(1 for t in final_tasks.values() if t["status"] == "SUCCESS")
        failure_count = sum(1 for t in final_tasks.values() if t["status"] == "FAILURE")
        assert success_count + failure_count == expected_count

        # For any failure during severed connection, assert explicit descriptive error
        for t in final_tasks.values():
            if t["status"] == "FAILURE":
                assert t.get("result") is not None and len(str(t["result"])) > 0

        # Assert document count for batch equals expected successful ingests
        toxic_resp = await client.get(
            f"{base_url}/api/documents/?title__icontains={run_tag}&page_size=1",
            headers=auth_headers,
            timeout=15.0,
        )
        assert toxic_resp.status_code == 200
        toxic_count = toxic_resp.json().get("count", 0)
        assert toxic_count == success_count, (
            f"Expected {success_count} documents for batch '{run_tag}', got {toxic_count}"
        )

        assert_target("tasks_stuck_after_fault", 0)


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-003")
@pytest.mark.asyncio
async def test_retry_idempotency_single_file(
    base_url: str,
    auth_headers: dict[str, str],
) -> None:
    """Test C: Upload one file, simulate client retry by uploading the same bytes again,

    and assert that there is exactly 1 document with that checksum.
    """
    token = f"TOKEN-RETRY-{time.time_ns()}"
    pdf_bytes = create_pdf_bytes(
        doc_id=9876,
        doc_type="invoice",
        correspondent="Acme Corp",
        date_str="2026-05-20",
        amount_str="$1,999.00",
        iban="DE89 3704 0044 0532 1234 56",
        unique_token=token,
    )
    md5_checksum = hashlib.md5(pdf_bytes).hexdigest()
    filename = "test_retry_single.pdf"

    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"

    async with httpx.AsyncClient() as client:
        # Step 1: Initial upload
        resp1 = await client.post(
            upload_url,
            headers=auth_headers,
            files={"document": (filename, pdf_bytes, "application/pdf")},
            timeout=30.0,
        )
        assert resp1.status_code == 200
        tid1 = resp1.json().strip()

        # Wait for task 1 to complete successfully
        final1 = await _wait_for_tasks_drained(client, tasks_url, auth_headers, {tid1}, timeout_s=60.0)
        assert final1[tid1]["status"] == "SUCCESS", f"Initial upload failed: {final1[tid1]}"
        doc_id = final1[tid1].get("related_document")
        assert doc_id is not None, "Initial upload produced no related document"

        # Verify initial document exists
        doc_resp = await client.get(f"{base_url}/api/documents/{doc_id}/", headers=auth_headers)
        assert doc_resp.status_code == 200

        # Step 2: Simulate client retry - upload exact same bytes again
        resp2 = await client.post(
            upload_url,
            headers=auth_headers,
            files={"document": (f"retry_{filename}", pdf_bytes, "application/pdf")},
            timeout=30.0,
        )
        assert resp2.status_code == 200
        tid2 = resp2.json().strip()

        # Wait for task 2 to finish - must be FAILURE with duplicate notice
        final2 = await _wait_for_tasks_drained(client, tasks_url, auth_headers, {tid2}, timeout_s=60.0)
        t2 = final2[tid2]
        assert t2["status"] == "FAILURE", f"Retry upload did not fail: {t2}"
        result_msg = str(t2.get("result", "")).lower()
        assert "duplicate" in result_msg, f"Failure message lacked 'duplicate': {t2.get('result')}"

        # Step 3: Assert exactly 1 document with that checksum in database via SQL
        sql_cmd = [
            "docker", "exec", "paperless-postgres",
            "psql", "-U", "paperless", "-d", "paperless", "-t", "-A",
            "-c", f"SELECT COUNT(*) FROM documents_document WHERE checksum = '{md5_checksum}'",
        ]
        res = await asyncio.to_thread(subprocess.run, sql_cmd, capture_output=True, text=True, check=True)
        matching_count = int(res.stdout.strip())
        assert matching_count == 1, (
            f"Expected exactly 1 document with checksum {md5_checksum}, found {matching_count}"
        )
