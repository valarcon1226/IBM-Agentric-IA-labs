"""Upload corpus/markdown/ into the Open WebUI knowledge collection `k8s-concepts`.

Nested paths cannot be filenames, so `a/b/c.md` is uploaded as `a__b__c.md`.
Idempotent: nothing happens when the collection already holds every file.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_DIR / "corpus" / "markdown"
COLLECTION = "k8s-concepts"
SEP = "__"


def to_filename(rel: str) -> str:
    return rel.replace("/", SEP)


def to_path(filename: str) -> str:
    return filename.replace(SEP, "/")


def login(base_url: str, timeout: float = 600.0) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=timeout)
    resp = client.post(
        "/api/v1/auths/signin",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    resp.raise_for_status()
    client.headers["Authorization"] = "Bearer " + resp.json()["token"]
    return client


def find_collection(client: httpx.Client) -> dict | None:
    resp = client.get("/api/v1/knowledge/")
    resp.raise_for_status()
    return next((k for k in resp.json() if k.get("name") == COLLECTION), None)


def file_count(client: httpx.Client, kid: str) -> int:
    resp = client.get(f"/api/v1/knowledge/{kid}")
    resp.raise_for_status()
    return len(resp.json().get("files") or [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="delete the collection first")
    parser.add_argument("--corpus", type=Path, default=CORPUS_DIR)
    args = parser.parse_args()

    files = sorted(p for p in args.corpus.rglob("*.md") if p.is_file())
    if not files:
        print(f"No markdown files under {args.corpus}", file=sys.stderr)
        return 1
    base_url = os.environ.get("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088")
    client = login(base_url)

    # Retrieval settings the protocol relies on. Both endpoints null any field left out,
    # so the full body goes back.
    settings = client.get("/api/v1/retrieval/query/settings").json()
    settings["k"] = 5
    client.post("/api/v1/retrieval/query/settings/update", json=settings).raise_for_status()
    tasks = client.get("/api/v1/tasks/config").json()
    tasks["ENABLE_RETRIEVAL_QUERY_GENERATION"] = False  # the query must be the question itself
    client.post("/api/v1/tasks/config/update", json=tasks).raise_for_status()

    existing = find_collection(client)
    if existing and args.recreate:
        client.delete(f"/api/v1/knowledge/{existing['id']}/delete").raise_for_status()
        existing = None
    if args.recreate:  # also drop files left behind by earlier or interrupted runs
        ours = {to_filename(p.relative_to(args.corpus).as_posix()) for p in files}
        for uploaded in client.get("/api/v1/files/").json():
            if uploaded.get("filename") in ours:
                client.delete(f"/api/v1/files/{uploaded['id']}")
    if existing:
        have = file_count(client, existing["id"])
        if have == len(files):
            print(f"{COLLECTION} already holds {have} files; nothing to do.")
            return 0
        print(f"{COLLECTION} holds {have}/{len(files)} files; rerun with --recreate.")
        return 1

    resp = client.post(
        "/api/v1/knowledge/create",
        json={"name": COLLECTION, "description": "Kubernetes concepts docs"},
    )
    resp.raise_for_status()
    kid = resp.json()["id"]

    for i, path in enumerate(files, 1):
        rel = path.relative_to(args.corpus).as_posix()
        up = client.post(
            "/api/v1/files/",
            files={"file": (to_filename(rel), path.read_bytes(), "text/markdown")},
        )
        up.raise_for_status()
        client.post(
            f"/api/v1/knowledge/{kid}/file/add", json={"file_id": up.json()["id"]}
        ).raise_for_status()
        print(f"[{i}/{len(files)}] {rel}", flush=True)
    print(f"Ingested {file_count(client, kid)} files into {COLLECTION}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
