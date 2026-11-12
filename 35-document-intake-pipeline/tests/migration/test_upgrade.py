"""Schema and application upgrade migration test suite (N-1 to N).

Tests upgrade from 2.14.6 (N-1) to 2.14.7 (N) on 500+ documents with tags,
notes, custom fields, media checksum verification, full-text searchability,
and database snapshot rollback.

Cited source:
- Version string: src/paperless/version.py (__full_version_str__)
- Migrations: src/documents/migrations/
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from qa_common.targets import assert_target


def _get_installed_version() -> str:
    res = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "shell", "-c",
            "from paperless import version; print(version.__full_version_str__)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _switch_webserver_image_and_wait(image_tag: str, base_url: str, timeout_s: float = 90.0) -> str:
    env = {**os.environ, "PAPERLESS_IMAGE": image_tag}
    subprocess.run(
        ["docker", "compose", "up", "-d", "webserver"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/", timeout=3.0)
            if resp.status_code == 200:
                v = _get_installed_version()
                return v
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(2.0)
    raise TimeoutError(f"Webserver did not become healthy with {image_tag} within {timeout_s}s")


@pytest.mark.migration
@pytest.mark.req("REQ-ING-010")
def test_schema_upgrade_n1_to_n(
    base_url: str,
    auth_headers: dict[str, str],
) -> None:
    """Upgrade Paperless-ngx from 2.14.6 to 2.14.7.

    Assert:
    - 0 metadata differences (counts of documents, tags, types, notes, custom fields)
    - 0 file differences (sha256 of downloaded archive/original files)
    - Full-text search retrieves 20 sampled unique tokens
    - Migration duration <= 300 s
    - Rollback restoring snapshot brings N-1 state back with identical counts
    """
    # Step 1: Verify version is N-1 (2.14.6)
    initial_version = _get_installed_version()
    if initial_version != "2.14.6":
        initial_version = _switch_webserver_image_and_wait(
            "ghcr.io/paperless-ngx/paperless-ngx:2.14.6", base_url
        )
    assert initial_version == "2.14.6", f"Expected N-1 version 2.14.6, got {initial_version}"
    print(f"\n[MIGRATION BASELINE] Confirmed running on N-1: {initial_version}")

    # Step 2: Ensure tags, notes, and custom fields exist on documents
    setup_script = (
        "from documents.models import Document, Tag, Note, CustomField, CustomFieldInstance; "
        "from django.contrib.auth import get_user_model; "
        "User = get_user_model(); u = User.objects.first(); "
        "tag, _ = Tag.objects.get_or_create(name='MigrationAuditTag'); "
        "cf, _ = CustomField.objects.get_or_create(name='MigrationField', data_type='string'); "
        "docs = list(Document.objects.all()[:100]); "
        "[d.tags.add(tag) for d in docs]; "
        "[Note.objects.create(document=d, note=f'Audit note {d.id}', user=u) for d in docs if not Note.objects.filter(document=d).exists()]; "
        "[CustomFieldInstance.objects.get_or_create(field=cf, document=d, defaults={'value_text': f'val-{d.id}'}) for d in docs]"
    )
    subprocess.run(
        ["docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "shell", "-c", setup_script],
        capture_output=True,
        text=True,
        check=True,
    )
    # Sync search index on N-1 baseline
    subprocess.run(
        ["docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "document_index", "reindex", "--no-progress-bar"],
        capture_output=True,
        text=True,
        check=True,
    )

    with httpx.Client(timeout=30.0) as client:
        # Step 3: Record pre-upgrade state and counts
        doc_list_resp = client.get(f"{base_url}/api/documents/?page_size=1000", headers=auth_headers)
        assert doc_list_resp.status_code == 200
        pre_docs = doc_list_resp.json().get("results", [])
        pre_doc_count = doc_list_resp.json().get("count", len(pre_docs))
        assert pre_doc_count >= 500, f"Expected at least 500 documents, found {pre_doc_count}"

        # Count metadata entities via Django ORM
        count_script = (
            "from documents.models import Document, Tag, DocumentType, Note, CustomField, CustomFieldInstance; "
            "import json; "
            "print(json.dumps({"
            "'docs': Document.objects.count(), "
            "'tags': Tag.objects.count(), "
            "'types': DocumentType.objects.count(), "
            "'notes': Note.objects.count(), "
            "'cfs': CustomField.objects.count(), "
            "'cfis': CustomFieldInstance.objects.count()"
            "}))"
        )
        counts_res = subprocess.run(
            ["docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "shell", "-c", count_script],
            capture_output=True,
            text=True,
            check=True,
        )
        pre_counts = json.loads(counts_res.stdout.strip())
        print(f"[PRE-UPGRADE COUNTS] {pre_counts}")

        # Sample 20 unique tokens (document titles) from pre_docs
        sampled_docs = pre_docs[:20]
        tokens_to_verify: list[tuple[int, str]] = []
        pre_checksums: dict[int, str] = {}

        for d in sampled_docs:
            did = d["id"]
            title = d.get("title", "")
            tokens_to_verify.append((did, title))
            down_resp = client.get(f"{base_url}/api/documents/{did}/download/", headers=auth_headers)
            assert down_resp.status_code == 200
            pre_checksums[did] = hashlib.sha256(down_resp.content).hexdigest()

        # Step 4: Take pre-upgrade database snapshot
        snapshot_dir = Path(__file__).resolve().parent.parent.parent / "results"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "snapshot_n1.sql"

        pg_dump_cmd = [
            "docker", "compose", "exec", "-T", "postgres",
            "pg_dump", "-U", "paperless", "--clean", "--if-exists", "paperless",
        ]
        dump_res = subprocess.run(pg_dump_cmd, capture_output=True, text=True, check=True)
        snapshot_file.write_text(dump_res.stdout, encoding="utf-8")
        assert snapshot_file.stat().st_size > 0, "Snapshot file is empty"
        print(f"[SNAPSHOT] Written {snapshot_file.stat().st_size} bytes to {snapshot_file.name}")

        # Step 5: Switch container to version N (2.14.7)
        upgraded_version = _switch_webserver_image_and_wait(
            "ghcr.io/paperless-ngx/paperless-ngx:2.14.7", base_url
        )
        assert upgraded_version == "2.14.7", f"Expected upgraded version 2.14.7, got {upgraded_version}"
        print(f"[CONTAINER SWITCH] Successfully transitioned to N: {upgraded_version}")

        # Step 6: Run upgrade migrations on N and measure duration
        start_mig = time.time()
        mig_cmd = [
            "docker", "compose", "exec", "-T", "webserver",
            "python3", "manage.py", "migrate",
        ]
        mig_res = subprocess.run(mig_cmd, capture_output=True, text=True, check=True)
        migration_duration_s = time.time() - start_mig
        print(f"[UPGRADE MIGRATION] Completed in {migration_duration_s:.2f} s: {mig_res.stdout.strip()}")
        assert_target("upgrade_duration_seconds", migration_duration_s)

        # Sync search index on N post-upgrade
        subprocess.run(
            ["docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "document_index", "reindex", "--no-progress-bar"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Step 7: Verify post-upgrade fidelity on N
        post_counts_res = subprocess.run(
            ["docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "shell", "-c", count_script],
            capture_output=True,
            text=True,
            check=True,
        )
        post_counts = json.loads(post_counts_res.stdout.strip())
        print(f"[POST-UPGRADE COUNTS] {post_counts}")

        # Assert 0 metadata differences
        assert post_counts["docs"] == pre_counts["docs"], f"Doc count diff: {pre_counts} vs {post_counts}"
        assert post_counts["tags"] == pre_counts["tags"], f"Tag count diff: {pre_counts} vs {post_counts}"
        assert post_counts["types"] == pre_counts["types"], f"Type count diff: {pre_counts} vs {post_counts}"
        assert post_counts["notes"] == pre_counts["notes"], f"Note count diff: {pre_counts} vs {post_counts}"
        assert post_counts["cfs"] == pre_counts["cfs"], f"CustomField count diff: {pre_counts} vs {post_counts}"
        assert post_counts["cfis"] == pre_counts["cfis"], f"CFInstance count diff: {pre_counts} vs {post_counts}"

        # Checksum comparison for 20 sampled documents (0 file differences)
        for did, pre_sha in pre_checksums.items():
            down_post = client.get(f"{base_url}/api/documents/{did}/download/", headers=auth_headers)
            assert down_post.status_code == 200
            post_sha = hashlib.sha256(down_post.content).hexdigest()
            assert post_sha == pre_sha, f"Checksum mismatch for doc {did}: {pre_sha} != {post_sha}"

        # Search for 20 sampled tokens
        for did, title in tokens_to_verify:
            search_resp = client.get(f"{base_url}/api/documents/?query={title}", headers=auth_headers)
            assert search_resp.status_code == 200
            found_ids = [doc["id"] for doc in search_resp.json().get("results", [])]
            assert did in found_ids, f"Document {did} with title '{title}' not found in search post-upgrade"

        print("[POST-UPGRADE VERIFIED] 0 metadata differences, 0 checksum differences, 20/20 search hits.")

        # Step 8: Rollback verification
        # Restore snapshot to PostgreSQL
        restore_cmd = [
            "docker", "compose", "exec", "-T", "postgres",
            "psql", "-U", "paperless", "-d", "paperless",
        ]
        restore_res = subprocess.run(
            restore_cmd,
            input=snapshot_file.read_bytes(),
            capture_output=True,
            check=True,
        )
        assert restore_res.returncode == 0, f"Snapshot restore failed: {restore_res.stderr.decode()}"

        # Switch webserver back to N-1 (2.14.6)
        rollback_version = _switch_webserver_image_and_wait(
            "ghcr.io/paperless-ngx/paperless-ngx:2.14.6", base_url
        )
        assert rollback_version == "2.14.6", f"Expected rollback version 2.14.6, got {rollback_version}"

        # Verify rollback state
        rollback_counts_res = subprocess.run(
            ["docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "shell", "-c", count_script],
            capture_output=True,
            text=True,
            check=True,
        )
        rollback_counts = json.loads(rollback_counts_res.stdout.strip())
        print(f"[ROLLBACK COUNTS] {rollback_counts}")
        assert rollback_counts == pre_counts, f"Rollback counts mismatch: {rollback_counts} != {pre_counts}"
        print("[ROLLBACK VERIFIED] Snapshot restored successfully with identical counts on N-1.")

        # Finally, transition stack back to N (2.14.7) for downstream UI tests
        final_version = _switch_webserver_image_and_wait(
            "ghcr.io/paperless-ngx/paperless-ngx:2.14.7", base_url
        )
        assert final_version == "2.14.7"
        print(f"[FINAL STATE] Webserver ready on N: {final_version}")
