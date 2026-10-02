"""Integration and E2E tests against the real docker-compose stack.

These tests talk to the actual API container (http://localhost:8001), the real
Postgres (localhost:5433) and Redis (localhost:6379) started by
``docker compose``. They read connection settings from ``E2E_*`` environment
variables, falling back to the values documented in ``.env.example``, and skip
cleanly (instead of failing) when the stack is not reachable so the unit suite
still runs without Docker.
"""

import json
import os
import time
from pathlib import Path

import httpx
import psycopg2
import pytest
from minio import Minio
from redis import Redis

pytestmark = pytest.mark.integration

## NOTE: dedicated E2E_* names are used (instead of the bare DATABASE_URL/API_KEY/etc.
## names) because tests/conftest.py sets process-wide fallback values for those bare
## names to satisfy app.config.Settings() for the *unit* suite; reusing them here would
## silently send the unit-test fallback (e.g. API_KEY=test) to the real running stack
## instead of the .env.example value it actually started with.
API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://localhost:8001")
API_KEY = os.environ.get("E2E_API_KEY", "change_me_api_key")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

POSTGRES_HOST = os.environ.get("E2E_POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("E2E_POSTGRES_PORT", "5433")
POSTGRES_USER = os.environ.get("E2E_POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("E2E_POSTGRES_PASSWORD", "change_me_postgres_password")
POSTGRES_DB = os.environ.get("E2E_POSTGRES_DB", "intake_db")

REDIS_HOST = os.environ.get("E2E_REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("E2E_REDIS_PORT", "6379"))

MINIO_ENDPOINT = os.environ.get("E2E_MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("E2E_MINIO_ACCESS_KEY", "change_me_minio_access_key")
MINIO_SECRET_KEY = os.environ.get("E2E_MINIO_SECRET_KEY", "change_me_minio_secret_key")
MINIO_BUCKET_NAME = os.environ.get("E2E_MINIO_BUCKET_NAME", "intake-files")

CUSTOMERS_CSV = Path(__file__).resolve().parents[2] / "customers.csv"


def _pg_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )


def _poll_until_completed(upload_id: str, timeout: float = 30) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/intake/{upload_id}", headers=HEADERS, timeout=5
        )
        response.raise_for_status()
        payload = response.json()
        if payload["status"] == "completed":
            return payload
        time.sleep(0.5)
    raise AssertionError(f"Upload {upload_id} did not complete within {timeout}s")


def _cleanup(upload_id: str | None) -> None:
    if upload_id is None:
        return
    try:
        with _pg_connection() as conn, conn.cursor() as cur:
            # ON DELETE CASCADE on clean_data/error_log removes their rows too.
            cur.execute("DELETE FROM uploads WHERE upload_id = %s", (upload_id,))
            conn.commit()
    except Exception:
        pass
    try:
        redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        for raw in redis_client.lrange("review_queue", 0, -1):
            text = raw.decode() if isinstance(raw, bytes) else raw
            if json.loads(text).get("upload_id") == upload_id:
                redis_client.lrem("review_queue", 1, raw)
    except Exception:
        pass
    try:
        minio_client = Minio(
            MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False
        )
        minio_client.remove_object(MINIO_BUCKET_NAME, upload_id)
    except Exception:
        pass


@pytest.fixture(scope="module")
def stack() -> str:
    try:
        httpx.get(f"{API_BASE_URL}/health", timeout=2).raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Docker stack not reachable at {API_BASE_URL}: {exc}")
    return API_BASE_URL


def test_health_endpoint_reports_healthy(stack: str) -> None:
    response = httpx.get(f"{stack}/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_upload_requires_api_key(stack: str) -> None:
    response = httpx.post(f"{stack}/api/v1/intake/upload", timeout=5)
    assert response.status_code == 401


@pytest.mark.e2e
def test_upload_review_and_approve_flow_against_real_stack(stack: str) -> None:
    upload_id = None
    try:
        with CUSTOMERS_CSV.open("rb") as fh:
            response = httpx.post(
                f"{stack}/api/v1/intake/upload",
                headers=HEADERS,
                files={"file": ("customers.csv", fh, "text/csv")},
                timeout=10,
            )
        assert response.status_code == 202
        upload_id = response.json()["upload_id"]

        status = _poll_until_completed(upload_id)
        assert status["clean_rows"] == 1
        assert status["ambiguous_rows"] == 1
        assert status["failed_rows"] == 1

        review = httpx.get(f"{stack}/api/v1/intake/{upload_id}/review", headers=HEADERS, timeout=5)
        assert review.status_code == 200
        pending = review.json()["pending_reviews"]
        assert len(pending) == 1
        record_id = pending[0]["record_id"]

        approve = httpx.post(
            f"{stack}/api/v1/intake/{upload_id}/review",
            headers=HEADERS,
            json={"record_id": record_id, "action": "approve"},
            timeout=5,
        )
        assert approve.status_code == 200
        assert approve.json()["message"] == "Record approved and moved to clean_data"

        review_after = httpx.get(
            f"{stack}/api/v1/intake/{upload_id}/review", headers=HEADERS, timeout=5
        )
        assert review_after.json()["pending_reviews"] == []

        with _pg_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM clean_data WHERE upload_id = %s", (upload_id,))
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT COUNT(*) FROM error_log WHERE upload_id = %s", (upload_id,))
            assert cur.fetchone()[0] == 1
    finally:
        _cleanup(upload_id)
