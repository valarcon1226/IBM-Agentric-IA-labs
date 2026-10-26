"""Kubernetes concepts documentation corpus downloader, converter, and Open WebUI ingestor.

Downloads the Kubernetes concepts documentation at the pinned commit from evals/config.toml,
strips Hugo frontmatter and shortcodes to produce clean plain markdown, adds 5 deliberately
unparseable files to test partial ingestion failure handling, and ingests all documents into
an Open WebUI knowledge collection.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("corpus")

# Base directories relative to script location or repo root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_DIR / "evals" / "config.toml"
CORPUS_DIR = PROJECT_DIR / "corpus"
RAW_DIR = CORPUS_DIR / "raw"
MARKDOWN_DIR = CORPUS_DIR / "markdown"
UNPARSEABLE_DIR = CORPUS_DIR / "unparseable"
RESULTS_DIR = PROJECT_DIR / "results"


def load_config() -> dict[str, Any]:
    """Loads repository, commit, and path from evals/config.toml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)
    return config.get("corpus", {})


def fetch_file_tree(repo: str, commit: str, subpath: str) -> list[str]:
    """Fetches the recursive git tree for the specified subpath from GitHub API."""
    url = f"https://api.github.com/repos/{repo}/git/trees/{commit}:{subpath}?recursive=1"
    headers = {
        "User-Agent": "llm-platform-evals-corpus-ingestor",
        "Accept": "application/vnd.github.v3+json",
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    logger.info("Fetching repository tree from GitHub API: %s", url)
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch tree from GitHub API (HTTP {resp.status_code}): {resp.text}"
            )
        data = resp.json()
        tree = data.get("tree", [])
        # Keep only markdown files (blobs ending in .md)
        md_paths = [
            item["path"]
            for item in tree
            if item.get("type") == "blob" and item.get("path", "").endswith(".md")
        ]
        logger.info("Discovered %d markdown files under %s", len(md_paths), subpath)
        return sorted(md_paths)


def download_single_file(
    repo: str, commit: str, subpath: str, rel_path: str, client: httpx.Client
) -> tuple[str, str]:
    """Downloads a single markdown file from raw.githubusercontent.com or local cache."""
    target_raw_path = RAW_DIR / rel_path
    if target_raw_path.exists() and target_raw_path.stat().st_size > 0:
        return rel_path, target_raw_path.read_text(encoding="utf-8")

    raw_url = f"https://raw.githubusercontent.com/{repo}/{commit}/{subpath}/{rel_path}"
    resp = client.get(raw_url, timeout=20.0)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to download {rel_path} from {raw_url} (HTTP {resp.status_code})"
        )
    content = resp.text
    target_raw_path.parent.mkdir(parents=True, exist_ok=True)
    target_raw_path.write_text(content, encoding="utf-8")
    return rel_path, content


def download_corpus(
    repo: str, commit: str, subpath: str, rel_paths: list[str]
) -> dict[str, str]:
    """Downloads all markdown files with concurrent worker pool."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    total = len(rel_paths)
    logger.info("Downloading %d files with concurrency...", total)

    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            future_to_path = {
                pool.submit(
                    download_single_file, repo, commit, subpath, path, client
                ): path
                for path in rel_paths
            }
            for idx, future in enumerate(
                concurrent.futures.as_completed(future_to_path), 1
            ):
                path = future_to_path[future]
                try:
                    rel_p, content = future.result()
                    results[rel_p] = content
                    if idx % 50 == 0 or idx == total:
                        logger.info("Downloaded %d/%d files", idx, total)
                except Exception as e:
                    logger.error("Error downloading %s: %s", path, e)
                    raise
    return results


def convert_to_plain_markdown(raw_content: str) -> str:
    """Converts Hugo-flavored Kubernetes docs markdown to clean plain markdown."""
    text = raw_content

    # Extract title and description from YAML frontmatter before stripping
    title = ""
    description = ""
    fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n?", text, flags=re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        # Match title
        t_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', fm_text, flags=re.MULTILINE)
        if t_match:
            title = t_match.group(1).strip()
        # Match description (single line or folded > block)
        d_match = re.search(
            r"^description:\s*(?:>\s*\n\s*([^\n]+)|[\"']?(.*?)[\"']?)\s*$",
            fm_text,
            flags=re.MULTILINE,
        )
        if d_match:
            description = (d_match.group(1) or d_match.group(2) or "").strip()

    # 1. Strip YAML frontmatter: ^---\n...\n---\n
    text = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, flags=re.DOTALL)

    # 2. Convert Hugo glossary tooltip shortcodes:
    # {{< glossary_tooltip text="foo" term_id="bar" >}} -> foo
    text = re.sub(
        r'\{\{<\s*glossary_tooltip\s+text="([^"]+)"[^>]*>\}\}',
        r"\1",
        text,
    )

    # 3. Strip other glossary shortcodes: {{< glossary_definition ... >}}
    text = re.sub(r"\{\{<\s*glossary_definition[^>]*>\}\}", "", text)

    # 4. Handle callout blocks: {{% note %}} / {{% /note %}} -> quote markers
    text = re.sub(
        r"\{\{[%<]\s*(?:note|caution|warning|important)\s*[%>]\}\}",
        "> **Note:** ",
        text,
    )
    text = re.sub(
        r"\{\{[%<]\s*/(?:note|caution|warning|important)\s*[%>]\}\}",
        "\n",
        text,
    )

    # 5. Remove remaining Hugo shortcodes: {{< ... >}} and {{% ... %}}
    text = re.sub(r"\{\{<[^>]+>\}\}", "", text)
    text = re.sub(r"\{\{%[^%]+%\}\}", "", text)

    # 6. Remove HTML comment tags: <!-- ... -->
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # 7. Normalize excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # 8. Ensure document is not empty; prepend title and description if body was minimal
    header_parts = []
    if title and not re.search(r"^#\s+", text):
        header_parts.append(f"# {title}")
    if description and description not in text:
        header_parts.append(description)

    if header_parts:
        prefix = "\n\n".join(header_parts)
        text = f"{prefix}\n\n{text}".strip() if text else prefix

    return text + "\n"


def build_plain_markdown_corpus(raw_files: dict[str, str]) -> dict[str, str]:
    """Converts all raw markdown files into plain markdown files on disk."""
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    converted: dict[str, str] = {}
    for rel_path, raw_text in raw_files.items():
        clean_text = convert_to_plain_markdown(raw_text)
        dest_path = MARKDOWN_DIR / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(clean_text, encoding="utf-8")
        converted[rel_path] = clean_text
    logger.info("Successfully converted %d files to plain markdown", len(converted))
    return converted


def create_unparseable_files() -> list[tuple[str, bytes, str, str]]:
    """Creates 5 deliberately unparseable files designed to trigger parser failures.

    Returns:
        List of tuples: (filename, binary_content, content_type, expected_failure_description)
    """
    UNPARSEABLE_DIR.mkdir(parents=True, exist_ok=True)
    unparseable_specs = [
        (
            "unparseable_01_corrupt_stream.pdf",
            b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\n"
            b"endobj\n%%EOF_CORRUPT_TRUNCATED",
            "application/pdf",
            "Truncated PDF with missing cross-reference table and premature EOF",
        ),
        (
            "unparseable_02_invalid_zip.docx",
            b"PK\x03\x04\x14\x00\x00\x00\x08\x00CORRUPT_NOT_A_VALID_ZIP_HEADER_OR_CENTRAL_DIRECTORY",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Corrupted DOCX archive with invalid ZIP central directory structure",
        ),
        (
            "unparseable_03_corrupt_container.epub",
            b"PK\x03\x04NOT_AN_EPUB_MAGIC_MIMETYPE_CORRUPTED_CONTAINER",
            "application/epub+zip",
            "Corrupted EPUB container lacking required META-INF and mimetype",
        ),
        (
            "unparseable_04_binary_encoding.md",
            bytes([0x80, 0x81, 0x82, 0x83, 0xFF, 0xFE, 0x00, 0x01, 0xFD, 0xFC]),
            "text/markdown",
            "Malformed non-UTF-8 binary sequence failing TextLoader charset detection",
        ),
        (
            "unparseable_05_unknown_excel.xlsx",
            b"PK\x03\x04CORRUPTED_SPREADSHEET_PAYLOAD_INVALID_XML_SHEET",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Corrupted XLSX spreadsheet format unparseable by Excel document loader",
        ),
    ]

    for fname, content, _, _ in unparseable_specs:
        path = UNPARSEABLE_DIR / fname
        path.write_bytes(content)

    logger.info("Created 5 deliberately unparseable test files in %s", UNPARSEABLE_DIR)
    return unparseable_specs


def get_openwebui_token(base_url: str) -> str:
    """Authenticates with Open WebUI and returns a valid Bearer token."""
    signin_url = f"{base_url}/api/v1/auths/signin"
    signup_url = f"{base_url}/api/v1/auths/signup"
    credentials = {"email": "admin@example.com", "password": "AdminPassword123!"}

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(signin_url, json=credentials)
        if resp.status_code == 200:
            token = resp.json().get("token")
            if token:
                return str(token)

        # Attempt signup if user does not exist yet
        signup_payload = {
            "name": "Admin",
            "email": credentials["email"],
            "password": credentials["password"],
        }
        resp = client.post(signup_url, json=signup_payload)
        if resp.status_code == 200:
            token = resp.json().get("token")
            if token:
                return str(token)

        raise RuntimeError(
            f"Failed to authenticate with Open WebUI at {base_url}: {resp.text}"
        )


def get_or_create_knowledge_collection(
    base_url: str, token: str, name: str, description: str
) -> str:
    """Creates a fresh Open WebUI knowledge collection and returns its ID."""
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=15.0) as client:
        # Check and delete existing collections with the same name to guarantee clean state
        resp = client.get(f"{base_url}/api/v1/knowledge/", headers=headers)
        if resp.status_code == 200:
            for item in resp.json():
                if item.get("name") == name:
                    coll_id = item["id"]
                    logger.info("Cleaning up existing collection '%s' (ID: %s)", name, coll_id)
                    client.delete(f"{base_url}/api/v1/knowledge/{coll_id}/delete", headers=headers)

        # Create new collection
        create_payload = {"name": name, "description": description}
        resp = client.post(
            f"{base_url}/api/v1/knowledge/create", headers=headers, json=create_payload
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to create knowledge collection: {resp.status_code} {resp.text}"
            )
        coll_id = resp.json()["id"]
        logger.info("Created new knowledge collection '%s' (ID: %s)", name, coll_id)
        return str(coll_id)


def upload_file_to_openwebui(
    base_url: str,
    token: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> dict[str, Any]:
    """Uploads a file to Open WebUI /api/v1/files/."""
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, content, content_type)}
    with httpx.Client(timeout=45.0) as client:
        resp = client.post(f"{base_url}/api/v1/files/", headers=headers, files=files)
        if resp.status_code != 200:
            return {
                "id": None,
                "filename": filename,
                "error": f"HTTP {resp.status_code}: {resp.text}",
            }
        return resp.json()


def add_file_to_knowledge(
    base_url: str, token: str, collection_id: str, file_id: str
) -> dict[str, Any]:
    """Links an uploaded file to the knowledge collection."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"file_id": file_id}
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{base_url}/api/v1/knowledge/{collection_id}/file/add",
            headers=headers,
            json=payload,
        )
        return {"status_code": resp.status_code, "data": resp.json()}


def ingest_corpus_and_assert(
    base_url: str,
    token: str,
    collection_id: str,
    valid_markdown_files: dict[str, str],
    unparseable_files: list[tuple[str, bytes, str, str]],
) -> dict[str, Any]:
    """Ingests valid and unparseable files into Open WebUI collection and asserts results."""
    logger.info("Beginning ingestion into collection ID: %s", collection_id)
    t0 = time.time()

    ingested_valid_ids: list[str] = []
    failed_reports: list[dict[str, Any]] = []

    # 1. Upload valid files with thread pool
    uploaded_valid: list[tuple[str, str]] = []

    def upload_valid_item(item: tuple[str, str]) -> tuple[str, str, bool, str]:
        rel_path, clean_text = item
        safe_filename = rel_path.replace("/", "__")
        up_res = upload_file_to_openwebui(
            base_url,
            token,
            safe_filename,
            clean_text.encode("utf-8"),
            "text/markdown",
        )
        if up_res.get("error"):
            return rel_path, "", False, up_res["error"]

        file_id = up_res.get("id")
        if not file_id:
            return rel_path, "", False, "No file ID returned"

        return rel_path, file_id, True, ""

    total_valid = len(valid_markdown_files)
    logger.info("Uploading %d valid files with worker pool...", total_valid)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [
            pool.submit(upload_valid_item, item)
            for item in valid_markdown_files.items()
        ]
        for idx, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            rel_p, fid, ok, err = fut.result()
            if ok:
                uploaded_valid.append((rel_p, fid))
            else:
                logger.error("Valid file %s failed upload: %s", rel_p, err)
                failed_reports.append(
                    {"filename": rel_p, "reason": err, "expected_valid": True}
                )
            if idx % 50 == 0 or idx == total_valid:
                logger.info("Uploaded %d/%d valid files", idx, total_valid)

    # 2. Link valid files sequentially to prevent database race conditions in Open WebUI
    logger.info(
        "Linking %d uploaded files to knowledge collection sequentially...",
        len(uploaded_valid),
    )
    for idx, (rel_p, file_id) in enumerate(uploaded_valid, 1):
        link_res = add_file_to_knowledge(base_url, token, collection_id, file_id)
        if link_res["status_code"] == 200:
            ingested_valid_ids.append(file_id)
        else:
            detail = link_res["data"].get("detail", str(link_res["data"]))
            logger.error("Failed to link file %s (%s): %s", rel_p, file_id, detail)
            failed_reports.append(
                {"filename": rel_p, "reason": f"Link failed: {detail}", "expected_valid": True}
            )
        if idx % 50 == 0 or idx == len(uploaded_valid):
            logger.info("Linked %d/%d files to collection", idx, len(uploaded_valid))

    # 2. Ingest the 5 unparseable files
    logger.info(
        "Ingesting %d deliberately unparseable files...", len(unparseable_files)
    )
    for fname, content, content_type, desc in unparseable_files:
        up_res = upload_file_to_openwebui(
            base_url, token, fname, content, content_type
        )
        error_msg = up_res.get("error")
        bad_file_id = str(up_res.get("id") or "")

        if error_msg:
            logger.info(
                "Unparseable file '%s' rejected at upload as expected: %s",
                fname,
                error_msg,
            )
            failed_reports.append(
                {
                    "filename": fname,
                    "stage": "upload",
                    "reason": str(error_msg),
                    "description": desc,
                    "expected_failure": True,
                }
            )
            continue

        # If upload returned 200 without error field, attempt linking to knowledge
        if bad_file_id:
            link_res = add_file_to_knowledge(base_url, token, collection_id, bad_file_id)
            if link_res["status_code"] != 200:
                reason = link_res["data"].get("detail", str(link_res["data"]))
                logger.info(
                    "Unparseable file '%s' rejected at knowledge linking as expected: %s",
                    fname,
                    reason,
                )
                failed_reports.append(
                    {
                        "filename": fname,
                        "stage": "knowledge_link",
                        "reason": reason,
                        "description": desc,
                        "expected_failure": True,
                    }
                )
            else:
                msg = f"Deliberately unparseable file '{fname}' was accepted into collection!"
                raise AssertionError(msg)
        else:
            failed_reports.append(
                {
                    "filename": fname,
                    "stage": "upload",
                    "reason": "Unknown upload rejection",
                    "description": desc,
                    "expected_failure": True,
                }
            )

    duration_s = time.time() - t0

    # 3. Query knowledge collection to assert exact file counts
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{base_url}/api/v1/knowledge/{collection_id}", headers=headers
        )
        assert (
            resp.status_code == 200
        ), f"Failed to retrieve collection: {resp.status_code}"
        coll_data = resp.json()
        collection_files = coll_data.get("files", [])

    logger.info("=" * 60)
    logger.info("INGESTION VERIFICATION AND ASSERTIONS:")
    logger.info(
        "Valid files submitted: %d, successfully linked: %d",
        total_valid,
        len(ingested_valid_ids),
    )
    logger.info(
        "Files present in collection: %d",
        len(collection_files),
    )
    logger.info(
        "Deliberate unparseable failures detected: %d / %d",
        len(failed_reports),
        len(unparseable_files),
    )
    logger.info("=" * 60)

    # Core assertions per Prompt 9 requirements:
    # 1. Assert every valid file was successfully ingested into collection
    assert (
        len(ingested_valid_ids) == total_valid
    ), f"Expected {total_valid} valid files, got {len(ingested_valid_ids)}"
    assert len(collection_files) == total_valid, (
        f"Collection holds {len(collection_files)} files, expected {total_valid} valid files"
    )

    # 2. Assert exactly the 5 unparseable files failed with explicit reasons
    unparseable_failures = [
        f for f in failed_reports if f.get("expected_failure") is True
    ]
    assert len(unparseable_failures) == len(unparseable_files), (
        f"Expected {len(unparseable_files)} unparseable failures, got {len(unparseable_failures)}"
    )
    for failure in unparseable_failures:
        assert failure.get("filename"), "Failure report missing filename"
        assert failure.get("reason"), f"Failure report for {failure['filename']} missing reason"

    result_summary = {
        "collection_id": collection_id,
        "collection_name": coll_data.get("name"),
        "valid_files_count": total_valid,
        "unparseable_files_count": len(unparseable_files),
        "collection_files_count": len(collection_files),
        "failed_files": unparseable_failures,
        "ingestion_duration_s": round(duration_s, 2),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / "ingestion.json"
    results_path.write_text(json.dumps(result_summary, indent=2), encoding="utf-8")
    logger.info("Ingestion results recorded in %s", results_path)

    return result_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kubernetes docs corpus download, conversion, and Open WebUI ingestion."
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Download and convert files only, skipping Open WebUI API ingestion.",
    )
    parser.add_argument(
        "--collection-name",
        default="kubernetes-concepts",
        help="Name of the Open WebUI knowledge collection.",
    )
    args = parser.parse_args()

    config = load_config()
    repo = config.get("repo", "kubernetes/website")
    commit = config.get("commit", "7fde177e22dc98390a6d55d215dd0301b5f6d0bb")
    subpath = config.get("path", "content/en/docs/concepts")

    logger.info("Corpus configuration: repo=%s commit=%s path=%s", repo, commit, subpath)

    # Step 1: Fetch file tree
    md_paths = fetch_file_tree(repo, commit, subpath)

    # Step 2: Download raw files
    raw_files = download_corpus(repo, commit, subpath, md_paths)

    # Step 3: Convert to plain markdown
    clean_files = build_plain_markdown_corpus(raw_files)

    # Step 4: Create 5 unparseable files
    unparseable_files = create_unparseable_files()

    if args.skip_ingest:
        logger.info("Skipping Open WebUI ingestion as requested by --skip-ingest.")
        return

    # Step 5: Ingest into Open WebUI knowledge collection
    openwebui_base_url = os.getenv("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    token = get_openwebui_token(openwebui_base_url)
    collection_id = get_or_create_knowledge_collection(
        openwebui_base_url,
        token,
        args.collection_name,
        "Kubernetes documentation concepts corpus",
    )

    ingest_corpus_and_assert(
        openwebui_base_url,
        token,
        collection_id,
        clean_files,
        unparseable_files,
    )


if __name__ == "__main__":
    main()
