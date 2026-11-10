from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import routes
from app.main import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer test"}
CALLBACK_BASE = "http://n8n:5678/webhook-waiting/"


def fake_upload_dependencies(monkeypatch):
    calls = []

    class Store:
        def bucket_exists(self, name):
            return True

        def put_object(self, bucket, name, stream, length):
            stream.read()

    class Connection:
        def execute(self, statement, parameters):
            pass

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    monkeypatch.setattr(routes.db, "get_minio", Store)
    monkeypatch.setattr(routes.db, "get_engine", Engine)
    monkeypatch.setattr(
        routes,
        "process_upload",
        lambda upload_id, callback_url=None: calls.append((upload_id, callback_url)),
    )
    monkeypatch.setattr(routes.settings, "N8N_RESUME_BASE_URL", CALLBACK_BASE, raising=False)
    return calls


def test_upload_requires_api_key():
    assert client.post("/api/v1/intake/upload").status_code == 401


def test_upload_stores_original_and_creates_upload(monkeypatch):
    calls = []
    tasks = fake_upload_dependencies(monkeypatch)

    class Store:
        def bucket_exists(self, name):
            return True

        def put_object(self, bucket, name, stream, length):
            calls.append((bucket, name, stream.read(), length))

    class Connection:
        def execute(self, statement, parameters):
            calls.append(parameters)

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    monkeypatch.setattr(routes.db, "get_minio", Store)
    monkeypatch.setattr(routes.db, "get_engine", Engine)
    result = client.post(
        "/api/v1/intake/upload",
        files={"file": ("customers.csv", b"first_name,last_name\nJane,Smith", "text/csv")},
        headers=HEADERS,
    )
    assert result.status_code == 202
    assert result.json()["status"] == "processing"
    assert calls[0][2] == b"first_name,last_name\nJane,Smith"
    assert calls[0][3] == len(calls[0][2])
    assert str(calls[1]["id"]) == result.json()["upload_id"]
    assert (str(tasks[0][0]), tasks[0][1]) == (result.json()["upload_id"], None)


def test_upload_passes_validated_callback_url_to_background(monkeypatch):
    tasks = fake_upload_dependencies(monkeypatch)
    callback_url = f"{CALLBACK_BASE}execution-token"

    result = client.post(
        "/api/v1/intake/upload",
        files={"file": ("customers.csv", b"first_name,last_name\nJane,Smith", "text/csv")},
        data={"callback_url": callback_url},
        headers=HEADERS,
    )

    assert result.status_code == 202
    assert (str(tasks[0][0]), tasks[0][1]) == (result.json()["upload_id"], callback_url)


@pytest.mark.parametrize(
    "callback_url",
    [
        "http://attacker:5678/webhook-waiting/token",
        "http://n8n:9999/webhook-waiting/token",
        "http://n8n:5678/other/token",
    ],
)
def test_upload_rejects_callback_urls_outside_configured_base(monkeypatch, callback_url):
    fake_upload_dependencies(monkeypatch)

    result = client.post(
        "/api/v1/intake/upload",
        files={"file": ("customers.csv", b"first_name,last_name\nJane,Smith", "text/csv")},
        data={"callback_url": callback_url},
        headers=HEADERS,
    )

    assert result.status_code == 400
