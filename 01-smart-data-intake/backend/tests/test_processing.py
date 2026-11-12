import json
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app import routes, services
from app.models import ReviewItem, RowData, StatusResponse
from tests.test_routes import HEADERS, client


def test_process_upload_routes_rows_and_logs_duplicate(monkeypatch):
    upload_id = uuid4()
    updates, clean, errors, queue = [], [], [], []

    class Stored:
        def read(self):
            return (
                b"first_name,last_name,email,phone,company\n"
                b"John,Doe,john@example.com,+1-555-0198,Acme Corp\n"
                b"Jane,Smith,jane@smith,555-0199,\n"
                b",,invalid-email,,\n"
                b"John,Doe,john@example.com,+1-555-0198,Acme Corp\n"
            )

        def close(self):
            pass

        def release_conn(self):
            pass

    class Store:
        def get_object(self, bucket, name):
            assert name == str(upload_id)
            return Stored()

    class Queue:
        def lpush(self, name, raw):
            queue.append(json.loads(raw))

    class Connection:
        def execute(self, statement, params):
            updates.append(params)

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    monkeypatch.setattr(services.db, "get_minio", Store)
    monkeypatch.setattr(services.db, "get_redis", Queue)
    monkeypatch.setattr(services.db, "get_engine", Engine)
    monkeypatch.setattr(
        services, "insert_clean", lambda uid, line, row: clean.append(row) or len(clean) == 1
    )
    monkeypatch.setattr(services, "log_error", lambda uid, line, row, reason: errors.append(reason))
    monkeypatch.setattr(services.settings, "N8N_CALLBACK_URL", None)
    services.process_upload(upload_id)
    assert len(clean) == 2
    assert errors[0].startswith("Missing required fields")
    assert errors[1] == "Duplicate email in upload"
    assert queue[0]["reasons"] == ["Missing company", "Potentially invalid email domain"]
    assert updates[-1] == {"id": str(upload_id), "total": 4}


def test_process_upload_marks_upload_failed_when_storage_fails(monkeypatch):
    upload_id = uuid4()
    updates = []

    class Store:
        def get_object(self, bucket, name):
            raise OSError("MinIO unavailable")

    class Connection:
        def execute(self, statement, params):
            updates.append((str(statement), params))

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    monkeypatch.setattr(services.db, "get_minio", Store)
    monkeypatch.setattr(services.db, "get_engine", Engine)
    services.process_upload(upload_id)

    statement, params = updates[0]
    assert "SET status='failed'" in statement
    assert params == {"id": str(upload_id)}


@pytest.mark.parametrize(
    ("callback_url", "expected_url"),
    [
        (None, "http://n8n:5678/webhook/intake-callback"),
        (
            "http://n8n:5678/webhook-waiting/execution-token",
            "http://n8n:5678/webhook-waiting/execution-token",
        ),
    ],
)
def test_process_upload_posts_status_and_clean_rows_to_selected_callback(
    monkeypatch, callback_url, expected_url
):
    upload_id = uuid4()
    clean_row = {
        "line_number": 2,
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@example.com",
        "phone": "555-0199",
        "company": "Smith LLC",
    }
    requests = []

    class Stored:
        def read(self):
            return (
                b"first_name,last_name,email,phone,company\n"
                b"Jane,Smith,jane@example.com,555-0199,Smith LLC\n"
            )

        def close(self):
            pass

        def release_conn(self):
            pass

    class Store:
        def get_object(self, bucket, name):
            return Stored()

    class QueryResult:
        def mappings(self):
            return self

        def all(self):
            return [clean_row]

    class Connection:
        def execute(self, statement, params):
            if "SELECT line_number" in str(statement):
                assert params == {"id": str(upload_id)}
                return QueryResult()

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

        @contextmanager
        def connect(self):
            yield Connection()

    class Response:
        def raise_for_status(self):
            pass

    def post(url, *, json, timeout):
        requests.append((url, json, timeout))
        return Response()

    monkeypatch.setattr(services.db, "get_minio", Store)
    monkeypatch.setattr(services.db, "get_engine", Engine)
    monkeypatch.setattr(services, "insert_clean", lambda uid, line, row: True)
    monkeypatch.setattr(
        services.settings, "N8N_CALLBACK_URL", "http://n8n:5678/webhook/intake-callback"
    )
    monkeypatch.setattr(
        services.settings,
        "N8N_RESUME_BASE_URL",
        "http://n8n:5678/webhook-waiting/",
        raising=False,
    )
    monkeypatch.setattr(
        routes,
        "get_status",
        lambda uid: StatusResponse(
            upload_id=uid,
            status="completed",
            total_rows=1,
            clean_rows=1,
            ambiguous_rows=0,
            failed_rows=0,
        ),
    )
    monkeypatch.setattr(services.httpx, "post", post)

    services.process_upload(upload_id, callback_url)

    assert len(requests) == 1
    url, payload, timeout = requests[0]
    assert url == expected_url
    assert timeout == 5
    assert payload["upload_id"] == str(upload_id)
    assert payload["status"] == "completed"
    assert payload["clean_rows_count"] == 1
    assert payload["clean_rows"] == [clean_row]


def test_readme_review_body_and_queue_removal(monkeypatch):
    upload_id = uuid4()
    record_id = uuid4()
    item = ReviewItem(
        record_id=record_id,
        upload_id=upload_id,
        line_number=42,
        data=RowData(first_name="Jane", last_name="Smith", email="jane@smith", phone="555-0199"),
        reasons=["Missing company", "Potentially invalid email domain"],
    )
    saved, removed = [], []

    class Queue:
        def lrem(self, name, count, value):
            removed.append(value)

    monkeypatch.setattr(routes, "pending_items", lambda uid: [(item.model_dump_json(), item)])
    monkeypatch.setattr(routes, "insert_clean", lambda uid, line, row: saved.append(row) or True)
    monkeypatch.setattr(routes.db, "get_redis", Queue)
    result = client.post(
        f"/api/v1/intake/{upload_id}/review",
        headers=HEADERS,
        json={
            "record_id": str(record_id),
            "action": "approve",
            "corrected_data": {
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@smith.com",
                "phone": "555-0199",
                "company": "Smith LLC",
            },
        },
    )
    assert result.json() == {
        "status": "success",
        "message": "Record approved and moved to clean_data",
    }
    assert saved[0]["email"] == "jane@smith.com"
    assert removed == [item.model_dump_json()]
    assert (
        client.get(f"/api/v1/intake/{upload_id}/review", headers=HEADERS).json()["pending_reviews"][
            0
        ]["reasons"]
        == item.reasons
    )


def test_reject_and_unknown_record(monkeypatch):
    upload_id = uuid4()
    item = ReviewItem(
        record_id=uuid4(), upload_id=upload_id, line_number=2, data=RowData(), reasons=[]
    )
    logged = []

    class Queue:
        def lrem(self, name, count, value):
            pass

    monkeypatch.setattr(routes, "pending_items", lambda uid: [(item.model_dump_json(), item)])
    monkeypatch.setattr(routes, "log_error", lambda uid, line, row, reason: logged.append(reason))
    monkeypatch.setattr(routes.db, "get_redis", Queue)
    url = f"/api/v1/intake/{upload_id}/review"
    assert (
        client.post(
            url, headers=HEADERS, json={"record_id": str(uuid4()), "action": "reject"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            url, headers=HEADERS, json={"record_id": str(item.record_id), "action": "reject"}
        ).status_code
        == 200
    )
    assert logged == ["Rejected in review"]
