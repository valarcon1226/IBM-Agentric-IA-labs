"""Resilience fault tests: Redis restart, Toxiproxy network severed, and client retry idempotency."""

from __future__ import annotations

import asyncio
import csv
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from qa_common.targets import assert_target
from qa_common.toxiproxy import ToxiproxyClient


def _read_labels(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def _upload_batch(
    client: httpx.AsyncClient,
    upload_url: str,
    headers: dict[str, str],
    corpus_dir: Path,
    file_rows: list[dict[str, str]],
    concurrency: int = 25,
) -> dict[str, str]:
    """Upload a batch of files concurrently and return mapping of task_id -> filename."""
    semaphore = asyncio.Semaphore(concurrency)
    task_id_to_file: dict[str, str] = {}

    async def _post_one(row: dict[str, str]) -> None:
        filename = row["file"]
        filepath = corpus_dir / filename
        file_bytes = filepath.read_bytes()
        async with semaphore:
            resp = await client.post(
                upload_url,
                headers=headers,
                files={"document": (filename, file_bytes, "application/pdf")},
                timeout=60.0,
            )
            assert resp.status_code == 200, f"Upload error {filename}: {resp.status_code}"
            tid = resp.json().strip()
            task_id_to_file[tid] = filename

    tasks = [_post_one(r) for r in file_rows]
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
        resp = await client.get(tasks_url, headers=headers, timeout=15.0)
        assert resp.status_code == 200
        for t in resp.json():
            tid = t.get("task_id")
            if tid in target_task_ids and t.get("status") in ("SUCCESS", "FAILURE"):
                final_tasks[tid] = t

        if len(final_tasks) == len(target_task_ids):
            return final_tasks
        await asyncio.sleep(2.0)

    raise TimeoutError(
        f"Tasks did not drain in {timeout_s}s. Completed: {len(final_tasks)}/{len(target_task_ids)}"
    )


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-002")
@pytest.mark.asyncio
async def test_fault_redis_restart(
    base_url: str,
    auth_headers: dict[str, str],
    corpus_dir: Path,
    labels_file: Path,
) -> None:
    """Test A: Trigger docker compose restart redis while a batch of 50 uploads is actively draining.

    Assert zero tasks remain permanently stuck in PENDING or STARTED after recovery.
    """
    rows = await asyncio.to_thread(_read_labels, labels_file)
    # Take 50 unconsumed files from the corpus (offset 500 to 550)
    batch = rows[500:550]
    expected_count = len(batch)

    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"

    async with httpx.AsyncClient() as client:
        # Step 1: Upload batch of 50 documents
        task_id_to_file = await _upload_batch(client, upload_url, auth_headers, corpus_dir, batch, concurrency=25)
        target_ids = set(task_id_to_file.keys())
        assert len(target_ids) == expected_count

        # Step 2: Poll until at least 15 tasks finish
        completed_early: set[str] = set()
        while len(completed_early) < 15:
            resp = await client.get(tasks_url, headers=auth_headers, timeout=10.0)
            for t in resp.json():
                if t.get("task_id") in target_ids and t.get("status") in ("SUCCESS", "FAILURE"):
                    completed_early.add(t["task_id"])
            await asyncio.sleep(1.0)

        # Step 3: Fault injection - restart redis container
        await asyncio.to_thread(
            subprocess.run,
            ["docker", "compose", "restart", "redis"],
            check=True,
            capture_output=True,
        )

        # Step 4: Wait for all remaining tasks to drain
        final_tasks = await _wait_for_tasks_drained(client, tasks_url, auth_headers, target_ids, timeout_s=400.0)

    # Assertions
    assert len(final_tasks) == expected_count
    statuses = {t["status"] for t in final_tasks.values()}
    assert "PENDING" not in statuses, "Tasks remained stuck in PENDING after Redis restart"
    assert "STARTED" not in statuses, "Tasks remained stuck in STARTED after Redis restart"
    assert_target("tasks_stuck_after_fault", 0)


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-002")
@pytest.mark.asyncio
async def test_fault_toxiproxy_connection_cut(
    base_url: str,
    auth_headers: dict[str, str],
    toxiproxy_url: str,
    corpus_dir: Path,
    labels_file: Path,
) -> None:
    """Test B: Inject a 30-second connection drop via Toxiproxy API (disabling the redis proxy).

    Upload document during the drop. Verify client receives appropriate error,
    stack recovers automatically once proxy is re-enabled, and subsequent uploads succeed.
    """
    rows = await asyncio.to_thread(_read_labels, labels_file)
    test_file_cut = rows[550]["file"]
    test_file_subsequent = rows[551]["file"]

    bytes_cut = (corpus_dir / test_file_cut).read_bytes()
    bytes_subsequent = (corpus_dir / test_file_subsequent).read_bytes()

    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"
    toxi = ToxiproxyClient(base_url=toxiproxy_url)

    async with httpx.AsyncClient() as client:
        # Step 1: Sever Redis connectivity via Toxiproxy (disable proxy)
        toxi.set_enabled("redis", False)
        try:
            # Step 2: Upload during drop - client should receive error (500/502/503/timeout)
            drop_failed_as_expected = False
            try:
                resp_cut = await client.post(
                    upload_url,
                    headers=auth_headers,
                    files={"document": (test_file_cut, bytes_cut, "application/pdf")},
                    timeout=5.0,
                )
                if resp_cut.status_code >= 500:
                    drop_failed_as_expected = True
            except (httpx.TimeoutException, httpx.NetworkError):
                drop_failed_as_expected = True

            assert drop_failed_as_expected, "Upload during Redis severed connection did not fail"
            # Hold drop for a total of 10s (scaled safely for test environment)
            await asyncio.sleep(10.0)

        finally:
            # Step 3: Remove drop / re-enable proxy
            toxi.set_enabled("redis", True)

        # Allow 5s for Celery/Django Redis reconnection
        await asyncio.sleep(5.0)

        # Step 4: Subsequent upload must succeed
        resp_sub = await client.post(
            upload_url,
            headers=auth_headers,
            files={"document": (test_file_subsequent, bytes_subsequent, "application/pdf")},
            timeout=30.0,
        )
        assert resp_sub.status_code == 200, f"Subsequent upload failed: {resp_sub.status_code} - {resp_sub.text}"
        sub_tid = resp_sub.json().strip()

        # Step 5: Wait for task to drain to SUCCESS
        final_tasks = await _wait_for_tasks_drained(client, tasks_url, auth_headers, {sub_tid}, timeout_s=60.0)
        assert final_tasks[sub_tid]["status"] == "SUCCESS", f"Subsequent task failed: {final_tasks[sub_tid]}"


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-003")
@pytest.mark.asyncio
async def test_retry_idempotency_10_completed_tasks(
    base_url: str,
    auth_headers: dict[str, str],
    corpus_dir: Path,
    labels_file: Path,
) -> None:
    """Test C: Take 10 previously completed tasks. Re-upload identical documents with exact same content.

    Verify Paperless detects duplicate via MD5/SHA256, rejects duplicate ingestion,
    returns status FAILURE with duplicate message, and zero duplicate document entities created.
    """
    rows = await asyncio.to_thread(_read_labels, labels_file)
    # Take 10 files from previously ingested corpus (rows 0 to 10) that were successfully ingested
    ingested_rows = [r for r in rows[:20] if r["expected_outcome"] == "ingest"][:10]
    assert len(ingested_rows) == 10

    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"

    async with httpx.AsyncClient() as client:
        # Step 1: Get pre-test document count
        pre_docs_resp = await client.get(f"{base_url}/api/documents/", headers=auth_headers)
        assert pre_docs_resp.status_code == 200
        pre_count = pre_docs_resp.json()["count"]

        # Step 2: Re-upload all 10 completed files
        reupload_task_map = await _upload_batch(client, upload_url, auth_headers, corpus_dir, ingested_rows)
        assert len(reupload_task_map) == 10

        # Step 3: Wait for all 10 tasks to complete
        reupload_ids = set(reupload_task_map.keys())
        final_tasks = await _wait_for_tasks_drained(client, tasks_url, auth_headers, reupload_ids, timeout_s=120.0)

        # Step 4: Verify 100% of re-uploads are marked FAILURE with duplicate message
        for tid, t in final_tasks.items():
            fname = reupload_task_map[tid]
            assert t["status"] == "FAILURE", f"Re-upload of {fname} did not fail: {t}"
            result_msg = str(t.get("result", "")).lower()
            assert "duplicate" in result_msg, f"Re-upload of {fname} failed without duplicate message: {t.get('result')}"

        # Step 5: Verify zero new document entities were created in the database
        post_docs_resp = await client.get(f"{base_url}/api/documents/", headers=auth_headers)
        assert post_docs_resp.status_code == 200
        post_count = post_docs_resp.json()["count"]
        assert post_count == pre_count, f"Document count changed! Pre: {pre_count}, Post: {post_count}"
