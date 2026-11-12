"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.database import MemoryDatabase, set_db
from api.main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch):
    monkeypatch.setattr(settings, "API_BEARER_TOKEN", "test_bearer_token")
    monkeypatch.setattr(settings, "SMTP_HOST", "localhost")
    monkeypatch.setattr(settings, "SMTP_PORT", 1025)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://fake_llm:8080/v1")


@pytest.fixture
def memory_db():
    db = MemoryDatabase()
    set_db(db)
    yield db


@pytest.fixture
def client(memory_db):
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test_bearer_token"}


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def feeds_url(fixtures_dir, monkeypatch):
    """Serve tests/fixtures over local HTTP, the way a real feed is fetched."""
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from api.config import settings

    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", True)
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(fixtures_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
