from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from app.database import get_db
from app.main import app
from app.models import Base

pytestmark = pytest.mark.integration


def test_postgres_integration_full_crud_lifecycle() -> None:
    """Integration test connecting to a real ephemeral PostgreSQL container via testcontainers."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        db_url = postgres.get_connection_url()
        assert "postgresql" in db_url

        # Build engine connected to the real container
        pg_engine = create_engine(db_url, pool_pre_ping=True)
        Base.metadata.create_all(bind=pg_engine)
        PgSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

        def override_get_db() -> Generator[Session, None, None]:
            session = PgSessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db

        try:
            with TestClient(app) as client:
                # 1. Health check against real postgres
                health_res = client.get("/health")
                assert health_res.status_code == 200
                assert health_res.json()["service"] == "12-ci-cd-pipeline-api"

                # 2. Create deployment
                payload = {
                    "service_name": "payment-gateway",
                    "environment": "production",
                    "version": "1.4.0",
                    "status": "pending",
                    "deployed_by": "ci-runner",
                    "description": "Integration test deployment in Postgres",
                }
                create_res = client.post("/api/v1/deployments", json=payload)
                assert create_res.status_code == 201
                created_data = create_res.json()
                dep_id = created_data["id"]
                assert dep_id >= 1
                assert created_data["service_name"] == "payment-gateway"
                assert created_data["status"] == "pending"

                # 3. Read list
                list_res = client.get("/api/v1/deployments?environment=production")
                assert list_res.status_code == 200
                items = list_res.json()
                assert len(items) >= 1
                assert any(i["id"] == dep_id for i in items)

                # 4. Read single
                get_res = client.get(f"/api/v1/deployments/{dep_id}")
                assert get_res.status_code == 200
                assert get_res.json()["service_name"] == "payment-gateway"

                # 5. Update
                update_res = client.put(
                    f"/api/v1/deployments/{dep_id}",
                    json={"status": "successful", "description": "Verified in PostgreSQL"},
                )
                assert update_res.status_code == 200
                assert update_res.json()["status"] == "successful"
                assert update_res.json()["description"] == "Verified in PostgreSQL"

                # 6. Delete
                del_res = client.delete(f"/api/v1/deployments/{dep_id}")
                assert del_res.status_code == 204

                # 7. Verify deletion
                get_after_del = client.get(f"/api/v1/deployments/{dep_id}")
                assert get_after_del.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=pg_engine)
