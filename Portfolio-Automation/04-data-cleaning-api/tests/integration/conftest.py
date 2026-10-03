import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

INIT_SQL = Path(__file__).resolve().parents[2] / "init-db.sql"


@pytest.fixture(scope="session")
def pg_engine():
    """Postgres 16 with init-db.sql applied. Skips locally without Docker; fails in CI."""
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as e:
        if os.getenv("REQUIRE_DOCKER") == "1":
            raise
        pytest.skip(f"Docker not available: {e}")
    try:
        engine = create_engine(container.get_connection_url())
        with engine.begin() as conn:
            conn.exec_driver_sql(INIT_SQL.read_text(encoding="utf-8"))
        yield engine
        engine.dispose()
    finally:
        container.stop()


@pytest.fixture
def session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, expire_on_commit=False)
