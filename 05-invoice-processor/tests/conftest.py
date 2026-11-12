"""Pytest test configuration and fixtures."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["API_BEARER_TOKEN"] = "test_bearer_token"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.api.dependencies import get_db
from app.main import app
from app.models.database import Base

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Sets up an isolated database for every test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def mock_storage_ensure_bucket(monkeypatch):
    """Mocks MinIO ensure_bucket so tests do not hang on network."""
    monkeypatch.setattr("app.services.storage.storage_service.ensure_bucket", lambda: None)
    monkeypatch.setattr("app.main.storage_service.ensure_bucket", lambda: None)


@pytest.fixture
def db_session():
    """Provides a transactional database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client with database dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test_bearer_token"}


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
