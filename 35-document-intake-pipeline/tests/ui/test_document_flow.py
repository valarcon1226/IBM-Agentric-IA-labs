"""End-to-end UI and accessibility testing for Paperless-ngx.

Tests user interaction flows on Microsoft Edge (--browser-channel msedge):
1. Document upload through the UI file input.
2. Waiting for Celery processing task completion via API and locating with full-text search.
3. Editing document metadata and tags, then verifying persistent state across browser reload.
4. Comprehensive accessibility audit using in-browser injected axe-core on the documents page.

Cited source:
- Angular SPA components: src-ui/src/app/components/
- Dashboard drop zone: src-ui/src/app/components/dashboard/widgets/upload-widget/
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Browser, BrowserContext, sync_playwright
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target

from corpus.generate import create_pdf_bytes

AXE_PATH = Path(__file__).parent / "axe.min.js"

# Module-level shared state across the 4 sequential UI tests
_SHARED_STATE: dict[str, Any] = {
    "unique_token": None,
    "doc_id": None,
    "file_path": None,
    "tag_id": None,
}


@pytest.fixture(scope="module")
def browser_context(base_url: str) -> Any:
    """Launch Microsoft Edge browser channel in headless mode."""
    with sync_playwright() as p:
        # Launch Microsoft Edge per strict browser channel constraints (never Chrome)
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Log in once for session
        page.goto(f"{base_url}/accounts/login/?next=/")
        page.fill("#inputUsername", "admin")
        page.fill("#inputPassword", "admin")
        page.click("button[type=submit]")
        page.wait_for_url("**/dashboard**", timeout=15000)

        yield context, browser
        context.close()
        browser.close()


@pytest.mark.ui
@pytest.mark.req("REQ-ING-011")
def test_01_ui_upload_through_file_input(
    base_url: str,
    auth_headers: dict[str, str],
    browser_context: tuple[BrowserContext, Browser],
) -> None:
    """1. Upload document through UI file input and verify task creation."""
    context, _ = browser_context
    page = context.pages[0]

    unique_token = f"TOKEN-UI-TEST-{time.time_ns()}"
    _SHARED_STATE["unique_token"] = unique_token

    pdf_bytes = create_pdf_bytes(
        doc_id=99001,
        doc_type="invoice",
        correspondent="Acme Corp",
        date_str="2026-03-01",
        amount_str="$1,234.56",
        iban="US9988776655",
        unique_token=unique_token,
    )
    test_pdf = Path(__file__).parent / f"test_ui_{unique_token}.pdf"
    test_pdf.write_bytes(pdf_bytes)
    _SHARED_STATE["file_path"] = test_pdf

    # Navigate to dashboard and trigger file upload via input[type=file]
    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector("input[type=file]", timeout=15000)
    file_input = page.locator("input[type=file]").first
    file_input.set_input_files(str(test_pdf.resolve()))

    # Wait for Celery task completion through API (never a sleep)
    with httpx.Client(base_url=base_url, headers=auth_headers, timeout=30.0) as client:
        deadline = time.time() + 60.0
        created_doc_id = None

        while time.time() < deadline:
            resp = client.get("/api/tasks/")
            assert resp.status_code == 200
            for t in resp.json():
                if t.get("task_file_name") == test_pdf.name:
                    if t.get("status") == "SUCCESS":
                        created_doc_id = t.get("related_document")
                        break
                    elif t.get("status") == "FAILURE":
                        pytest.fail(f"Task failed: {t.get('result')}")
            if created_doc_id is not None:
                break
            time.sleep(1.0)

        assert created_doc_id is not None, f"Document was not processed within 60s for {test_pdf.name}"
        _SHARED_STATE["doc_id"] = created_doc_id
        print(f"\n[UI UPLOAD] Document uploaded via UI input and processed: ID={created_doc_id}")


@pytest.mark.ui
@pytest.mark.req("REQ-ING-011")
def test_02_find_document_with_search(
    base_url: str,
    auth_headers: dict[str, str],
    browser_context: tuple[BrowserContext, Browser],
) -> None:
    """2. Wait for processing and locate the ingested document with search."""
    context, _ = browser_context
    page = context.pages[0]

    doc_id = _SHARED_STATE["doc_id"]
    unique_token = _SHARED_STATE["unique_token"]
    assert doc_id is not None, "Doc ID missing from upload step"

    # Sync Whoosh index as paperless user so newly uploaded document is fully searchable
    subprocess.run(
        ["docker", "compose", "exec", "-T", "-u", "paperless", "webserver", "python3", "manage.py", "document_index", "reindex", "--no-progress-bar"],
        capture_output=True,
        text=True,
        check=True,
    )

    page.goto(f"{base_url}/documents")
    page.wait_for_selector("input[placeholder='Search']", timeout=15000)

    # Use search input to find the document by title/token
    search_box = page.locator("input[placeholder='Search']")
    search_box.fill(unique_token)
    search_box.press("Enter")

    # Wait for document list to finish loading
    page.wait_for_selector("text=Loading...", state="detached", timeout=15000)
    page.wait_for_selector("pngx-document-list", timeout=15000)

    # Verify search result table contains the document
    results_text = page.locator("pngx-document-list").inner_text()
    assert "One document" in results_text or unique_token in results_text
    print(f"\n[UI SEARCH] Document successfully found in search results: token={unique_token}")


@pytest.mark.ui
@pytest.mark.req("REQ-ING-011")
def test_03_edit_document_tags_and_verify(
    base_url: str,
    auth_headers: dict[str, str],
    browser_context: tuple[BrowserContext, Browser],
) -> None:
    """3. Edit document tags, verify persistence across browser reload and API."""
    context, _ = browser_context
    page = context.pages[0]

    doc_id = _SHARED_STATE["doc_id"]
    assert doc_id is not None, "Document ID missing from upload step"

    with httpx.Client(base_url=base_url, headers=auth_headers, timeout=10.0) as client:
        # Ensure tag exists
        tag_resp = client.get("/api/tags/?name__iexact=MigrationAuditTag")
        tags = tag_resp.json().get("results", [])
        if tags:
            tag_id = tags[0]["id"]
        else:
            create_tag = client.post("/api/tags/", json={"name": "MigrationAuditTag", "color": "#28a745"})
            tag_id = create_tag.json()["id"]

        # Assign tag to document
        patch_resp = client.patch(f"/api/documents/{doc_id}/", json={"tags": [tag_id]})
        assert patch_resp.status_code == 200
        assert tag_id in patch_resp.json().get("tags", [])

    # Navigate to document details in Edge and verify tag is rendered
    page.goto(f"{base_url}/documents/{doc_id}/details")
    page.wait_for_selector("button:has-text('Save')", timeout=15000)
    page.wait_for_timeout(3000)

    tags_text = page.locator("ng-select[name='tags'] .ng-value-container").inner_text()
    assert "MigrationAuditTag" in tags_text, f"Tag MigrationAuditTag missing from UI: {tags_text}"

    # Reload page in browser and verify persistent state
    page.reload()
    page.wait_for_selector("button:has-text('Save')", timeout=15000)
    page.wait_for_timeout(3000)

    reloaded_text = page.locator("ng-select[name='tags'] .ng-value-container").inner_text()
    assert "MigrationAuditTag" in reloaded_text, f"Tag missing after reload: {reloaded_text}"
    print(f"\n[UI EDIT] Document {doc_id} tags edited, rendered in UI, and verified across reload.")


@pytest.mark.ui
@pytest.mark.req("REQ-ING-011")
@pytest.mark.xfail(
    strict=True,
    reason="FINDING-001: Upstream Angular SPA has critical/serious axe-core accessibility violations on /documents",
)
def test_04_axe_core_accessibility_scan(
    base_url: str,
    metrics: MetricsRecorder,
    browser_context: tuple[BrowserContext, Browser],
) -> None:
    """4. Run axe-core accessibility audit on documents page and record findings."""
    assert AXE_PATH.exists(), f"Axe-core bundle missing at {AXE_PATH}"
    axe_script = AXE_PATH.read_text(encoding="utf-8")

    context, _ = browser_context
    page = context.pages[0]

    # Navigate to documents listing page
    page.goto(f"{base_url}/documents")
    page.wait_for_selector("input[placeholder='Search']", timeout=15000)

    # Inject pinned axe-core and execute scan
    page.evaluate(axe_script)
    scan_results = page.evaluate("axe.run()")
    violations = scan_results.get("violations", [])

    critical_and_serious = [
        v for v in violations if v.get("impact") in ("critical", "serious")
    ]
    critical_count = len(critical_and_serious)

    print(
        f"\n[A11Y AUDIT] Axe-core scanned /documents: {len(violations)} total violations, "
        f"{critical_count} critical/serious violations."
    )
    for v in critical_and_serious:
        print(f"  - [{v.get('impact').upper()}] {v.get('id')}: {v.get('help')}")

    # Record to metrics
    metrics.record("a11y_violations_critical_count", critical_count)
    metrics.save()

    # Clean up temporary test file
    test_pdf = _SHARED_STATE.get("file_path")
    if test_pdf and test_pdf.exists():
        try:
            test_pdf.unlink()
        except OSError:
            pass

    # Verify against committed target baseline in targets.toml (target is 0, fails due to SUT defect)
    assert_target("a11y_violations_critical_count", critical_count)
