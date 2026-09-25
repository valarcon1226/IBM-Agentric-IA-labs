import io

import pytest
from fastapi.testclient import TestClient

from app import main
from app.api.routes import clean, enrich, transform, upload
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.services import storage
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


def test_clean_large_file_is_queued_not_processed_inline(monkeypatch):
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


def test_create_schema():
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "int"}})
    assert res.json()["status"] == "success"


def test_list_schemas():
    assert client.get("/api/v1/schemas").status_code == 200


def test_unknown_job_result_returns_404():
    res = client.get("/api/v1/jobs/does-not-exist/result")
    assert res.status_code == 404


def test_api_rejects_missing_api_key():
    res = anon_client.get("/api/v1/schemas")
    assert res.status_code == 401


def test_api_rejects_wrong_api_key():
    res = anon_client.get("/api/v1/schemas", headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401


def test_health_does_not_require_api_key(healthy_dependencies):
    assert anon_client.get("/health").status_code == 200


def test_transform_accepts_documented_payload(monkeypatch):
    monkeypatch.setattr(transform.process_transform_job, "delay", lambda *args: None)
    res = client.post("/api/v1/transform", json=README_TRANSFORM_PAYLOAD)
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_enrich_accepts_documented_payload(monkeypatch):
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
