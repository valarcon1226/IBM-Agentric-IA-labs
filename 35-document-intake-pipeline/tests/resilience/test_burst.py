"""Resilience test: 500-document concurrent burst ingestion and accounting."""

from __future__ import annotations

import asyncio
import collections
import csv
import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target


def parse_docker_mem_mb(raw_str: str) -> float:
    """Parse docker stats memory string (e.g. '792.5MiB / 2GiB') to megabytes (MB)."""
    try:
        part = raw_str.split("/")[0].strip()
        if part.endswith("GiB"):
            return float(part[:-3].strip()) * 1024.0
        elif part.endswith("MiB"):
            return float(part[:-3].strip())
        elif part.endswith("KiB"):
            return float(part[:-3].strip()) / 1024.0
        elif part.endswith("B"):
            return float(part[:-1].strip()) / (1024.0 * 1024.0)
    except (ValueError, IndexError):
        return 0.0
    return 0.0


def _get_docker_mem() -> float:
    try:
        res = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "paperless-webserver"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
        if res.returncode == 0 and res.stdout.strip():
            return parse_docker_mem_mb(res.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        pass
    return 0.0


async def sample_memory_loop(
    stop_event: asyncio.Event,
    peak_memory_container: list[float],
    sample_interval_s: float = 5.0,
) -> None:
    """Sample paperless-webserver memory every 5 s using docker stats."""
    while not stop_event.is_set():
        mb = await asyncio.to_thread(_get_docker_mem)
        peak_memory_container[0] = max(peak_memory_container[0], mb)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sample_interval_s)
        except TimeoutError:
            pass


def _read_labels(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.resilience
@pytest.mark.req("REQ-ING-001")
@pytest.mark.asyncio
async def test_burst_500_upload_accounting(
    base_url: str,
    auth_headers: dict[str, str],
    corpus_dir: Path,
    labels_file: Path,
    metrics: MetricsRecorder,
) -> None:
    """Upload 500 corpus files concurrently with Semaphore(50), track all to final state,

    sample memory, and assert 100% accounting and performance targets.
    """
    rows = await asyncio.to_thread(_read_labels, labels_file)

    # Take first 500 files
    burst_rows = rows[:500]
    assert len(burst_rows) == 500, f"Expected 500 rows in corpus, found {len(burst_rows)}"
    expected_outcomes = {r["file"]: r["expected_outcome"] for r in burst_rows}

    # Task tracking mappings
    file_to_task_id: dict[str, str] = {}
    task_id_to_file: dict[str, str] = {}

    semaphore = asyncio.Semaphore(50)
    upload_url = f"{base_url}/api/documents/post_document/"

    async def upload_single(client: httpx.AsyncClient, file_info: dict[str, str]) -> None:
        filename = file_info["file"]
        filepath = corpus_dir / filename
        assert filepath.is_file(), f"Missing corpus file: {filepath}"
        file_bytes = filepath.read_bytes()

        async with semaphore:
            resp = await client.post(
                upload_url,
                headers=auth_headers,
                files={"document": (filename, file_bytes, "application/pdf")},
                timeout=60.0,
            )
            assert resp.status_code == 200, f"Failed upload for {filename}: {resp.status_code} - {resp.text}"
            task_id = resp.json().strip()
            file_to_task_id[filename] = task_id
            task_id_to_file[task_id] = filename

    start_time = time.time()
    peak_memory = [0.0]
    stop_memory_event = asyncio.Event()
    mem_task = asyncio.create_task(sample_memory_loop(stop_memory_event, peak_memory, sample_interval_s=5.0))

    try:
        # Phase 1: Burst upload of 500 files
        limits = httpx.Limits(max_connections=60, max_keepalive_connections=50)
        async with httpx.AsyncClient(limits=limits) as client:
            upload_tasks = [upload_single(client, r) for r in burst_rows]
            await asyncio.gather(*upload_tasks)

        assert len(task_id_to_file) == 500, f"Expected 500 task IDs, got {len(task_id_to_file)}"
        target_task_ids = set(task_id_to_file.keys())

        # Phase 2: Poll /api/tasks/ until every task is SUCCESS or FAILURE
        tasks_url = f"{base_url}/api/tasks/"
        timeout_seconds = 1800.0  # 30 minutes
        poll_deadline = time.time() + timeout_seconds

        final_tasks: dict[str, dict[str, Any]] = {}

        async with httpx.AsyncClient() as poll_client:
            while time.time() < poll_deadline:
                resp = await poll_client.get(tasks_url, headers=auth_headers, timeout=15.0)
                assert resp.status_code == 200, f"Failed to poll /api/tasks/: {resp.status_code}"
                task_list: list[dict[str, Any]] = resp.json()

                for t in task_list:
                    tid = t.get("task_id")
                    if tid in target_task_ids:
                        status = t.get("status")
                        if status in ("SUCCESS", "FAILURE"):
                            final_tasks[tid] = t

                if len(final_tasks) == len(target_task_ids):
                    break

                await asyncio.sleep(3.0)

        drain_time_s = time.time() - start_time
        assert len(final_tasks) == 500, (
            f"Timeout waiting for tasks to drain. Completed: {len(final_tasks)}/500 after {drain_time_s:.1f}s"
        )

    finally:
        stop_memory_event.set()
        await mem_task

    # Phase 3: Assertions and accounting
    successes = [t for t in final_tasks.values() if t["status"] == "SUCCESS"]
    failures = [t for t in final_tasks.values() if t["status"] == "FAILURE"]

    assert len(successes) + len(failures) == 500, (
        f"Sum of successes ({len(successes)}) and failures ({len(failures)}) != 500"
    )

    # Compute duplicate groups based on sha256 of files in burst set
    file_hashes = {
        r["file"]: hashlib.sha256((corpus_dir / r["file"]).read_bytes()).hexdigest()
        for r in burst_rows
    }
    hash_counts = collections.Counter(file_hashes.values())
    dup_files = {f for f, h in file_hashes.items() if hash_counts[h] > 1}

    # Every failure must belong to corrupt or duplicate
    for f_task in failures:
        tid = f_task["task_id"]
        fname = task_id_to_file[tid]
        expected = expected_outcomes[fname]
        is_dup = (expected == "duplicate") or (fname in dup_files)
        assert expected == "corrupt" or is_dup, (
            f"File {fname} with expected outcome '{expected}' unexpectedly failed: {f_task.get('result')}"
        )
        # Verify failure message names cause
        result_msg = str(f_task.get("result", "")).lower()
        if expected == "corrupt":
            assert any(
                term in result_msg
                for term in ("inputfileerror", "error occurred", "corrupt", "not a valid", "syntaxerror")
            ), f"Corrupt file failure message lacked cause: {f_task.get('result')}"
        elif is_dup:
            assert "duplicate" in result_msg, f"Duplicate file failure message lacked cause: {f_task.get('result')}"

    # Phase 4: Record metrics and assert against targets
    throughput_dpm = (500.0 / drain_time_s) * 60.0
    accounted_ratio = (len(successes) + len(failures)) / 500.0

    metrics.record("queue_drain_time_seconds", drain_time_s)
    metrics.record("throughput_docs_per_min_rate", throughput_dpm)
    metrics.record("peak_webserver_memory_mb", peak_memory[0])
    metrics.record("uploads_accounted_ratio", accounted_ratio)
    metrics.save()

    print(
        f"\n[BURST SUMMARY] Ingested 500 documents: {len(successes)} Successes, {len(failures)} Failures.\n"
        f"Drain Time: {drain_time_s:.2f}s ({drain_time_s/60:.2f} min), "
        f"Throughput: {throughput_dpm:.2f} docs/min, "
        f"Peak Webserver Memory: {peak_memory[0]:.1f} MB."
    )

    assert_target("uploads_accounted_ratio", accounted_ratio)
    assert_target("queue_drain_time_seconds", drain_time_s)
    assert_target("throughput_docs_per_min_rate", throughput_dpm)
    assert_target("peak_webserver_memory_mb", peak_memory[0])
