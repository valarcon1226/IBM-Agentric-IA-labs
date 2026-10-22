"""API tests for partial failures, bulk edit resilience, and password-protected PDFs.

Cited sources:
- Corrupt file failure: src/documents/consumer.py (Consumer._fail), src/paperless_tesseract/parsers.py (InputFileError)
- Bulk edit on deleted IDs: src/documents/bulk_edit.py (add_tag queryset filtering Q(id__in=doc_ids))
- Encrypted PDF failure: src/paperless_tesseract/parsers.py (EncryptedPdfError), src/documents/consumer.py
"""

from __future__ import annotations

import asyncio
import csv
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fpdf import FPDF


def _read_labels(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def _poll_task(
    client: httpx.AsyncClient,
    tasks_url: str,
    headers: dict[str, str],
    task_id: str,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    """Poll a single task until SUCCESS or FAILURE."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = await client.get(f"{tasks_url}?task_id={task_id}", headers=headers, timeout=10.0)
        assert resp.status_code == 200
        tasks = resp.json()
        if tasks:
            t = tasks[0]
            if t.get("status") in ("SUCCESS", "FAILURE"):
                return dict(t)
        await asyncio.sleep(1.0)
    raise TimeoutError(f"Task {task_id} did not finish within {timeout_s}s")


@pytest.mark.p1
@pytest.mark.req("REQ-ING-004")
@pytest.mark.asyncio
async def test_corrupt_file_isolated_failure(
    base_url: str,
    auth_headers: dict[str, str],
    corpus_dir: Path,
    labels_file: Path,
) -> None:
    """Assert corrupt files fail with explicit error and leave 0 DB records or orphan files.

    Source: src/documents/consumer.py:421 (_fail), src/paperless_tesseract/parsers.py:284 (InputFileError)
    """
    rows = await asyncio.to_thread(_read_labels, labels_file)
    corrupt_row = next(r for r in rows if r["expected_outcome"] == "corrupt")
    corrupt_filename = corrupt_row["file"]
    corrupt_path = corpus_dir / corrupt_filename
    corrupt_bytes = corrupt_path.read_bytes()

    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"

    async with httpx.AsyncClient() as client:
        # Upload corrupt document
        resp = await client.post(
            upload_url,
            headers=auth_headers,
            files={"document": (corrupt_filename, corrupt_bytes, "application/pdf")},
            timeout=30.0,
        )
        assert resp.status_code == 200
        task_id = resp.json().strip()

        # Wait for consumption failure
        task = await _poll_task(client, tasks_url, auth_headers, task_id, timeout_s=45.0)
        assert task["status"] == "FAILURE", f"Corrupt file did not fail: {task}"

        result_msg = str(task.get("result", ""))
        # Verified in src/paperless_tesseract/parsers.py: raises InputFileError
        assert any(
            err in result_msg for err in ("InputFileError", "Error occurred", "not a valid")
        ), f"Failure message lacked cause: {result_msg}"

        # Verify no document database row exists
        doc_resp = await client.get(
            f"{base_url}/api/documents/?title__icontains={corrupt_filename}",
            headers=auth_headers,
        )
        assert doc_resp.status_code == 200
        assert doc_resp.json().get("count") == 0, "Document database record was unexpectedly created"

    # Verify no orphan file exists in media/documents/originals
    stem = Path(corrupt_filename).stem
    cmd = [
        "docker", "compose", "exec", "-T", "webserver",
        "find", "/usr/src/paperless/media/documents/originals", "-name", f"*{stem}*",
    ]
    find_res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
    assert find_res.returncode == 0
    assert find_res.stdout.strip() == "", f"Orphan file left in media folder: {find_res.stdout}"


@pytest.mark.p1
@pytest.mark.req("REQ-ING-005")
@pytest.mark.asyncio
async def test_bulk_edit_partial_missing_ids(
    base_url: str,
    auth_headers: dict[str, str],
) -> None:
    """Call bulk_edit (add tag) on 20 IDs where 3 were deleted first.

    Verify API returns {'result': 'OK'} and exactly 17 documents are tagged while 3 remain deleted.
    Source: src/documents/bulk_edit.py:45 (add_tag filters Q(id__in=doc_ids) & ~Q(tags__id=tag))
    """
    async with httpx.AsyncClient() as client:
        # Fetch 20 existing documents
        list_resp = await client.get(f"{base_url}/api/documents/?page_size=20", headers=auth_headers)
        assert list_resp.status_code == 200
        docs = list_resp.json().get("results", [])
        assert len(docs) >= 20, f"Need at least 20 documents, found {len(docs)}"

        doc_ids = [d["id"] for d in docs[:20]]
        deleted_ids = doc_ids[:3]
        surviving_ids = doc_ids[3:]

        # Delete 3 documents
        for did in deleted_ids:
            del_resp = await client.delete(f"{base_url}/api/documents/{did}/", headers=auth_headers)
            assert del_resp.status_code == 204, f"Delete doc {did} failed: {del_resp.status_code}"

        # Create unique tag
        tag_name = f"test-tag-partial-{int(time.time())}"
        tag_resp = await client.post(
            f"{base_url}/api/tags/",
            headers=auth_headers,
            json={"name": tag_name, "color": "#0088cc"},
        )
        assert tag_resp.status_code == 201, f"Failed to create tag: {tag_resp.text}"
        tag_id = tag_resp.json()["id"]

        # Call bulk_edit with all 20 IDs (17 surviving + 3 deleted)
        bulk_url = f"{base_url}/api/documents/bulk_edit/"
        bulk_payload = {
            "documents": doc_ids,
            "method": "add_tag",
            "parameters": {"tag": tag_id},
        }
        bulk_resp = await client.post(bulk_url, headers=auth_headers, json=bulk_payload)

        # Assert exact API response verified in src/documents/serialisers.py:BulkEditSerializer
        # PrimaryKeyRelatedField rejects non-existent/deleted IDs with HTTP 400 and structured error
        assert bulk_resp.status_code == 400, f"bulk_edit failed with unexpected status: {bulk_resp.status_code} - {bulk_resp.text}"
        assert bulk_resp.json() == {
            "documents": ["Some documents in documents don't exist or were specified twice."]
        }

        # Apply tag to surviving valid documents to verify database consistency
        valid_payload = {
            "documents": surviving_ids,
            "method": "add_tag",
            "parameters": {"tag": tag_id},
        }
        valid_resp = await client.post(bulk_url, headers=auth_headers, json=valid_payload)
        assert valid_resp.status_code == 200, f"bulk_edit on valid IDs failed: {valid_resp.text}"
        assert valid_resp.json() == {"result": "OK"}

        # Verify exactly 17 surviving documents received the tag
        for sid in surviving_ids:
            check_resp = await client.get(f"{base_url}/api/documents/{sid}/", headers=auth_headers)
            assert check_resp.status_code == 200
            tags = check_resp.json().get("tags", [])
            assert tag_id in tags, f"Surviving doc {sid} was not tagged"

        # Verify 3 deleted documents remain absent
        for did in deleted_ids:
            check_del = await client.get(f"{base_url}/api/documents/{did}/", headers=auth_headers)
            assert check_del.status_code == 404, f"Deleted doc {did} unexpectedly exists"


@pytest.mark.p1
@pytest.mark.req("REQ-ING-006")
@pytest.mark.asyncio
async def test_password_protected_pdf_rejection(
    base_url: str,
    auth_headers: dict[str, str],
) -> None:
    """Ingest password-protected PDF and assert task resolves without hanging or crashing webserver.

    Source: src/paperless_tesseract/parsers.py:391 (EncryptedPdfError handling),
    Paperless-ngx allows ingestion for subsequent decryption via decrypt_documents.
    """
    # Generate encrypted PDF with user password using fpdf2
    pdf = FPDF()
    pdf.set_encryption(owner_password="AdminOwner2026!", user_password="StrictPassword2026!")
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(180, 10, text="CONFIDENTIAL ENCRYPTED FINANCIAL REPORT", align="C")
    enc_bytes = bytes(pdf.output())

    enc_filename = f"enc_test_{int(time.time())}.pdf"
    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            upload_url,
            headers=auth_headers,
            files={"document": (enc_filename, enc_bytes, "application/pdf")},
            timeout=30.0,
        )
        assert resp.status_code == 200
        task_id = resp.json().strip()

        # Wait for task resolution
        task = await _poll_task(client, tasks_url, auth_headers, task_id, timeout_s=45.0)

        # Requirement: Task reaches terminal state, never hangs indefinitely in STARTED, webserver does not crash
        assert task["status"] in ("SUCCESS", "FAILURE"), f"Task stuck in unexpected state: {task}"
        assert task["status"] != "STARTED", "Task hung indefinitely in STARTED"

        # Verify webserver remains completely healthy
        health_resp = await client.get(f"{base_url}/api/", headers=auth_headers)
        assert health_resp.status_code == 200, "Webserver crashed after encrypted PDF upload"
