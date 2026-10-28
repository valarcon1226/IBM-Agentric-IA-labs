"""Shared pytest fixtures for Paperless-ngx document intake pipeline test suite."""

from __future__ import annotations

import asyncio
import csv
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("PAPERLESS_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def toxiproxy_url() -> str:
    return os.getenv("TOXIPROXY_URL", "http://127.0.0.1:8474").rstrip("/")


@pytest.fixture(scope="session")
def admin_credentials() -> tuple[str, str]:
    return (
        os.getenv("PAPERLESS_ADMIN_USER", "admin"),
        os.getenv("PAPERLESS_ADMIN_PASSWORD", "admin"),
    )


@pytest.fixture(scope="session")
def api_token(base_url: str, admin_credentials: tuple[str, str]) -> str:
    # Check .token file first
    token_path = Path(__file__).resolve().parent.parent / ".token"
    if token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            # Verify if existing token is valid against Paperless API
            try:
                resp = httpx.get(
                    f"{base_url}/api/documents/?page_size=1",
                    headers={"Authorization": f"Token {token}"},
                    timeout=5.0,
                )
                if resp.status_code in (401, 403):
                    pytest.fail(
                        f"El token en .token ya no autentica contra Paperless-ngx (HTTP {resp.status_code}). "
                        "Por favor ejecute 'scripts/setup.py' para recrear el usuario y regenerar el token."
                    )
                if resp.status_code == 200:
                    return token
            except (httpx.HTTPError, OSError):
                pass

            # Fallback verification against status endpoint
            try:
                resp = httpx.get(
                    f"{base_url}/api/status/",
                    headers={"Authorization": f"Token {token}"},
                    timeout=5.0,
                )
                if resp.status_code in (401, 403):
                    pytest.fail(
                        f"El token en .token ya no autentica contra Paperless-ngx (HTTP {resp.status_code}). "
                        "Por favor ejecute 'scripts/setup.py' para recrear el usuario y regenerar el token."
                    )
                if resp.status_code == 200:
                    return token
            except (httpx.HTTPError, OSError):
                pass

    token_env = os.getenv("PAPERLESS_API_TOKEN")
    if token_env:
        return token_env.strip()

    # Obtain via /api/token/
    username, password = admin_credentials
    try:
        resp = httpx.post(
            f"{base_url}/api/token/",
            json={"username": username, "password": password},
            timeout=10.0,
        )
        if resp.status_code in (400, 401, 403):
            pytest.fail(
                f"No se pudo autenticar usuario admin en Paperless-ngx (HTTP {resp.status_code}). "
                "Por favor ejecute 'scripts/setup.py' para inicializar el stack y generar el token."
            )
        resp.raise_for_status()
        token = str(resp.json()["token"]).strip()
        token_path.write_text(token, encoding="utf-8")
        return token
    except (httpx.HTTPError, OSError) as exc:
        pytest.fail(
            f"Fallo al autenticar contra Paperless-ngx: {exc}. "
            "Por favor ejecute 'scripts/setup.py'."
        )


@pytest.fixture(scope="session")
def auth_headers(api_token: str) -> dict[str, str]:
    return {"Authorization": f"Token {api_token}"}


@pytest.fixture(scope="session")
def corpus_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "corpus" / "generated"


@pytest.fixture(scope="session")
def labels_file() -> Path:
    return Path(__file__).resolve().parent.parent / "corpus" / "labels.csv"


async def _upload_and_drain_corpus(
    base_url: str,
    headers: dict[str, str],
    corpus_dir: Path,
    rows: list[dict[str, str]],
    concurrency: int = 50,
    timeout_s: float = 900.0,
) -> None:
    """Upload corpus files concurrently and poll tasks until terminal state."""
    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"
    semaphore = asyncio.Semaphore(concurrency)
    task_ids: set[str] = set()

    limits = httpx.Limits(max_connections=60, max_keepalive_connections=50)
    async with httpx.AsyncClient(limits=limits) as client:
        async def _upload_file(row: dict[str, str]) -> None:
            filename = row["file"]
            filepath = corpus_dir / filename
            if not filepath.is_file():
                return
            file_bytes = filepath.read_bytes()
            async with semaphore:
                resp = await client.post(
                    upload_url,
                    headers=headers,
                    files={"document": (filename, file_bytes, "application/pdf")},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    tid = resp.json().strip()
                    task_ids.add(tid)

        print(f"\n[CORPUS FIXTURE] Subiendo {len(rows)} documentos del corpus a Paperless-ngx...")
        await asyncio.gather(*[_upload_file(r) for r in rows])

        print(f"[CORPUS FIXTURE] Esperando procesamiento de {len(task_ids)} tareas en Celery...")
        deadline = time.time() + timeout_s
        final_tasks: dict[str, dict[str, Any]] = {}
        last_log = time.time()
        while time.time() < deadline:
            resp = await client.get(tasks_url, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                for t in resp.json():
                    tid = t.get("task_id")
                    if tid in task_ids and t.get("status") in ("SUCCESS", "FAILURE"):
                        final_tasks[tid] = t

            if len(final_tasks) == len(task_ids):
                break

            if time.time() - last_log > 10.0:
                print(f"[CORPUS FIXTURE] Progreso: {len(final_tasks)}/{len(task_ids)} tareas completadas...")
                last_log = time.time()

            await asyncio.sleep(2.0)

        if len(final_tasks) < len(task_ids):
            raise TimeoutError(
                f"Las tareas del corpus no finalizaron en {timeout_s}s. Completadas: {len(final_tasks)}/{len(task_ids)}"
            )

        print(f"[CORPUS FIXTURE] Procesamiento finalizado con exito: {len(final_tasks)} tareas resueltas.")

        # Ensure Whoosh search index is fully synchronized for full-text queries
        for _ in range(30):
            s_resp = await client.get(
                f"{base_url}/api/documents/?query=COMMERCIAL%20UTILITY%20STATEMENT",
                headers=headers,
                timeout=10.0,
            )
            if s_resp.status_code == 200 and s_resp.json().get("count", 0) >= 80:
                break
            await asyncio.sleep(1.0)


@pytest.fixture(scope="session", autouse=True)
def ensure_corpus_loaded(
    request: pytest.FixtureRequest,
    base_url: str,
    corpus_dir: Path,
    labels_file: Path,
) -> None:
    """Session fixture that ensures required corpus documents are ingested and processed.

    Enables every test suite (api, faults, migration, eval, ui) to run standalone
    on a clean stack without mocks.
    """
    # 1. Skip if session only contains unit tests that don't need SUT (e.g. test_corpus.py)
    test_nodeids = [item.nodeid for item in request.session.items]
    if all("test_corpus.py" in nid for nid in test_nodeids):
        return

    # 2. Skip if session contains test_burst.py, which specifically tests burst ingestion on clean queue
    if any("test_burst" in nid for nid in test_nodeids):
        return

    # Requested here, not as an argument, so the skips above never need a running stack.
    auth_headers: dict[str, str] = request.getfixturevalue("auth_headers")

    # 3. Ensure corpus files exist on disk; generate if missing
    if not labels_file.is_file() or not corpus_dir.is_dir() or len(list(corpus_dir.glob("*.pdf"))) < 500:
        from corpus.generate import generate_corpus
        corpus_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = corpus_dir.parent / "manifest.sha256"
        generate_corpus(seed=42, count=600, output_dir=corpus_dir, labels_file=labels_file, manifest_file=manifest_file)

    with open(labels_file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Target: 520 valid documents of type 'ingest' from corpus (ensures >= 500 and >= 80 utility bills)
    target_rows = [r for r in rows if r.get("expected_outcome") == "ingest"][:520]
    target_files = {r["file"] for r in target_rows}

    # 4. Check existing documents in Paperless-ngx
    existing_filenames: set[str] = set()
    db_url = os.getenv("DATABASE_URL", "postgresql://paperless:paperless_password@127.0.0.1:5433/paperless")
    try:
        with psycopg.connect(db_url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT original_filename FROM documents_document WHERE original_filename IS NOT NULL")
            existing_filenames = {row[0] for row in cur.fetchall()}
    except (psycopg.Error, OSError) as exc:
        logger.debug("SQL check for existing documents failed, falling back to API: %s", exc)
        # Fallback to API check
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{base_url}/api/documents/?page_size=1000", headers=auth_headers)
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    existing_filenames = {d["original_file_name"] for d in results if d.get("original_file_name")}
        except (httpx.HTTPError, OSError) as api_exc:
            logger.debug("API check for existing documents also failed: %s", api_exc)

    corpus_present = target_files.intersection(existing_filenames)
    # If at least 480 corpus documents are already present, DB has sufficient corpus
    if len(corpus_present) >= 480:
        return

    missing_rows = [r for r in target_rows if r["file"] not in existing_filenames]
    if not missing_rows:
        return

    # 5. Ingest what is missing and wait for completion (no mocks)
    asyncio.run(_upload_and_drain_corpus(base_url, auth_headers, corpus_dir, missing_rows))
