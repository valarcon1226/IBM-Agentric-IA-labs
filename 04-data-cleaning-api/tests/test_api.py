import io
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main
from app.api.routes import clean, enrich, jobs, transform, upload
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.db import JobStatus
from app.services import jobs_repo, schemas_repo, storage
from tests.conftest import TEST_ENV

client = TestClient(app, headers={"Authorization": f"Bearer {TEST_ENV['API_KEY']}"})
anon_client = TestClient(app)

# Request bodies copied verbatim from README sections 6.3 and 6.4 — keep them in sync.
README_TRANSFORM_PAYLOAD = {
    "file_path": "uploads/1234-5678_dataset.csv",
    "operation": "pivot",
    "params": {"index": "date", "columns": "category", "values": "revenue"},
}
README_ENRICH_PAYLOAD = {
    "file_path": "uploads/1234-5678_contacts.csv",
    "operations": ["validate_emails", "normalize_phones"],
    "target_columns": {"email": "email_col", "phone": "phone_col"},
}


class _FakeSession:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def execute(self, statement: object) -> None:
        if self.fail:
            raise RuntimeError("db down")


class _FakeRedis:
    def ping(self) -> bool:
        return True


@pytest.fixture
def healthy_dependencies(monkeypatch):
    monkeypatch.setattr(main.redis, "from_url", lambda url: _FakeRedis())
    app.dependency_overrides[get_db] = lambda: _FakeSession()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def fake_jobs(monkeypatch):
    """Replace the jobs table with an in-memory call log; no database needed."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        jobs_repo,
        "create_job",
        lambda db, job_id, operation_type, input_file_path: calls.append(
            ("create", str(job_id), operation_type, input_file_path)
        ),
    )
    monkeypatch.setattr(
        jobs_repo,
        "set_status",
        lambda job_id, status, **kwargs: calls.append(("status", str(job_id), status, kwargs)),
    )
    app.dependency_overrides[get_db] = lambda: object()
    yield calls
    app.dependency_overrides.clear()


def test_production_app_exposes_versioned_routes():
    paths = {route.path for route in app.routes}
    expected = {
        "/api/v1/clean",
        "/api/v1/validate",
        "/api/v1/transform",
        "/api/v1/enrich",
        "/api/v1/upload",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/result",
        "/api/v1/schemas",
    }
    assert expected <= paths


def test_health_ok_when_dependencies_respond(healthy_dependencies):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok", "redis": "ok"}


def test_health_reports_503_when_database_fails(healthy_dependencies):
    app.dependency_overrides[get_db] = lambda: _FakeSession(fail=True)
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["detail"]["db"].startswith("error")


def test_clean_small_file_sync():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.csv", io.BytesIO(b"A\n1\n1\n"), "text/csv")},
        data={"options": '{"remove_duplicates": true}'},
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1


def test_clean_rejects_malformed_options_json():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.csv", io.BytesIO(b"A\n1\n"), "text/csv")},
        data={"options": "{not json"},
    )
    assert res.status_code == 400


def test_clean_large_file_is_queued_not_processed_inline(monkeypatch, fake_jobs):
    queued: list[tuple] = []
    monkeypatch.setattr(clean, "upload_file", lambda content, name: name)
    monkeypatch.setattr(clean.process_clean_job, "delay", lambda *args: queued.append(args))
    # Shrink the threshold so the test stays fast; the routing rule is what's under test.
    monkeypatch.setattr(clean, "MAX_SYNC_BYTES", 64)
    large_csv = b"A\n" + b"1\n" * 64

    res = client.post(
        "/api/v1/clean",
        files={"file": ("big.csv", io.BytesIO(large_csv), "text/csv")},
        data={"options": "{}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "processing"
    assert queued and queued[0][0] == body["job_id"]


def test_validate_valid_data():
    res = client.post(
        "/api/v1/validate",
        json={"schema_id": "user_schema", "data": [{"id": 1, "name": "A", "age": 10}]},
    )
    assert res.json()["status"] == "valid"


def test_validate_invalid_data():
    res = client.post(
        "/api/v1/validate",
        json={"schema_id": "user_schema", "data": [{"id": 1, "name": "A", "age": -1}]},
    )
    assert res.json()["status"] == "invalid"


def test_validate_unknown_schema_returns_404():
    res = client.post("/api/v1/validate", json={"schema_id": "missing", "data": []})
    assert res.status_code == 404


def test_create_schema(monkeypatch, fake_db):
    monkeypatch.setattr(
        schemas_repo,
        "create_schema",
        lambda db, name, fields: SimpleNamespace(
            schema_id=uuid4(), name=name, definition={"fields": fields}
        ),
    )
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "int"}})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["data"]["fields"] == {"id": "int"}


def test_list_schemas(monkeypatch, fake_db):
    monkeypatch.setattr(schemas_repo, "list_schemas", lambda db: [])
    res = client.get("/api/v1/schemas")
    assert res.status_code == 200
    assert res.json() == {"status": "success", "schemas": []}


def test_api_rejects_missing_api_key():
    res = anon_client.get("/api/v1/schemas")
    assert res.status_code == 401


def test_api_rejects_wrong_api_key():
    res = anon_client.get("/api/v1/schemas", headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401


def test_health_does_not_require_api_key(healthy_dependencies):
    assert anon_client.get("/health").status_code == 200


def test_transform_accepts_documented_payload(monkeypatch, fake_jobs):
    monkeypatch.setattr(transform.process_transform_job, "delay", lambda *args: None)
    res = client.post("/api/v1/transform", json=README_TRANSFORM_PAYLOAD)
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_enrich_accepts_documented_payload(monkeypatch, fake_jobs):
    monkeypatch.setattr(enrich.process_enrich_job, "delay", lambda *args: None)
    res = client.post("/api/v1/enrich", json=README_ENRICH_PAYLOAD)
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_transform_rejects_internal_task_shape():
    res = client.post("/api/v1/transform", json={"type": "pivot", "args": {}})
    assert res.status_code == 422


def test_clean_rejects_empty_file():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.csv", io.BytesIO(b""), "text/csv")},
        data={"options": "{}"},
    )
    assert res.status_code == 400


def test_clean_rejects_non_utf8_file():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.csv", io.BytesIO(b"\xff\xfe\xfa\n"), "text/csv")},
        data={"options": "{}"},
    )
    assert res.status_code == 400


def test_internal_errors_do_not_leak_details(monkeypatch):
    def boom(content, name):
        raise RuntimeError("secret-internal-detail")

    monkeypatch.setattr(upload, "upload_file", boom)
    res = client.post("/api/v1/upload", files={"file": ("t.csv", io.BytesIO(b"A\n1\n"))})
    assert res.status_code == 500
    assert "secret-internal-detail" not in res.text


def test_storage_uses_configured_bucket():
    assert storage.BUCKET_NAME == settings.MINIO_BUCKET


def test_async_clean_creates_pending_job_before_queueing(monkeypatch, fake_jobs):
    monkeypatch.setattr(clean, "upload_file", lambda content, name: name)
    monkeypatch.setattr(
        clean.process_clean_job, "delay", lambda *args: fake_jobs.append(("delay", *args))
    )
    monkeypatch.setattr(clean, "MAX_SYNC_BYTES", 64)

    res = client.post(
        "/api/v1/clean",
        files={"file": ("big.csv", io.BytesIO(b"A\n" + b"1\n" * 64), "text/csv")},
        data={"options": "{}"},
    )

    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert [c[0] for c in fake_jobs] == ["create", "delay"]
    assert fake_jobs[0][1:3] == (job_id, "clean")
    assert fake_jobs[1][1] == job_id


def test_enqueue_failure_marks_job_failed(monkeypatch, fake_jobs):
    def broker_down(*args):
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(transform.process_transform_job, "delay", broker_down)

    res = client.post("/api/v1/transform", json=README_TRANSFORM_PAYLOAD)

    assert res.status_code == 500
    assert [c[0] for c in fake_jobs] == ["create", "status"]
    assert fake_jobs[1][2] == JobStatus.FAILED


def _job(**overrides):
    base = {
        "job_id": uuid4(),
        "status": "COMPLETED",
        "operation_type": "clean",
        "error_message": None,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
        "output_file_path": "results/cleaned.csv",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def fake_db():
    app.dependency_overrides[get_db] = lambda: object()
    yield
    app.dependency_overrides.clear()


def test_get_job_returns_persisted_state(monkeypatch, fake_db):
    job = _job(status="PROCESSING")
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: job)

    res = client.get(f"/api/v1/jobs/{job.job_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "PROCESSING"
    assert body["job_id"] == str(job.job_id)
    assert "output_file_path" not in body


def test_unknown_job_returns_404(monkeypatch, fake_db):
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: None)
    assert client.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    assert client.get(f"/api/v1/jobs/{uuid4()}/result").status_code == 404


def test_invalid_job_id_returns_422(fake_db):
    assert client.get("/api/v1/jobs/not-a-uuid").status_code == 422


def test_job_result_not_completed_returns_400(monkeypatch, fake_db):
    job = _job(status="PROCESSING", output_file_path=None)
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: job)
    assert client.get(f"/api/v1/jobs/{job.job_id}/result").status_code == 400


def test_job_result_returns_presigned_url(monkeypatch, fake_db):
    job = _job()
    monkeypatch.setattr(jobs_repo, "get_job", lambda db, job_id: job)
    monkeypatch.setattr(
        jobs, "generate_presigned_url", lambda key, expires: f"https://minio.local/{key}"
    )

    res = client.get(f"/api/v1/jobs/{job.job_id}/result")

    assert res.status_code == 200
    assert res.json() == {
        "job_id": str(job.job_id),
        "download_url": "https://minio.local/results/cleaned.csv",
        "expires_in": 3600,
    }


def test_created_schema_is_usable_in_validate(monkeypatch, fake_db):
    sid = uuid4()
    stored = SimpleNamespace(
        schema_id=sid, name="customers", definition={"fields": {"id": "int", "email": "str"}}
    )
    monkeypatch.setattr(
        schemas_repo, "get_schema", lambda db, schema_id: stored if schema_id == sid else None
    )

    ok = client.post(
        "/api/v1/validate",
        json={"schema_id": str(sid), "data": [{"id": 1, "email": "a@b.co"}]},
    )
    bad = client.post(
        "/api/v1/validate",
        json={"schema_id": str(sid), "data": [{"id": "x", "email": "a@b.co"}]},
    )

    assert ok.json()["status"] == "valid"
    assert bad.json()["status"] == "invalid"


def test_create_schema_rejects_unknown_type(fake_db):
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "uuid"}})
    assert res.status_code == 422


def test_create_schema_duplicate_name_returns_409(monkeypatch, fake_db):
    def duplicate(db, name, fields):
        raise schemas_repo.DuplicateSchemaError(name)

    monkeypatch.setattr(schemas_repo, "create_schema", duplicate)
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "int"}})
    assert res.status_code == 409


def test_clean_accepts_xlsx():
    buf = io.BytesIO()
    pd.DataFrame({"A": [1, 1, 2]}).to_excel(buf, index=False)
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.xlsx", io.BytesIO(buf.getvalue()))},
        data={"options": '{"remove_duplicates": true}'},
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 2


def test_clean_accepts_json_records():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.json", io.BytesIO(b'[{"A": 1}, {"A": 1}, {"A": 2}]'))},
        data={"options": '{"remove_duplicates": true}'},
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 2


def test_clean_rejects_unsupported_extension():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.txt", io.BytesIO(b"A\n1\n"))},
        data={"options": "{}"},
    )
    assert res.status_code == 415
