from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy_celery_beat.models import ModelBase

from app.core.config import settings
from app.main import app
from app.models.database import Base, get_db


@pytest.fixture
def test_db(monkeypatch: pytest.MonkeyPatch) -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    ).execution_options(schema_translate_map={"celery_schema": None})

    Base.metadata.create_all(bind=engine)
    ModelBase.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr("app.models.database.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("app.core.celery_app.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("app.models.database.engine", engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"Authorization": f"Bearer {settings.API_KEY}"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def jobs_dir() -> Path:
    return settings.jobs_path
