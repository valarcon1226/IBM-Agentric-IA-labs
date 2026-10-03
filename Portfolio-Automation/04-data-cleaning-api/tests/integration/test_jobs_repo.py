from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.db import JobModel, JobStatus, SchemaModel
from app.services import jobs_repo

pytestmark = pytest.mark.integration


def test_job_lifecycle_is_persisted(session_factory):
    job_id = uuid4()
    with session_factory() as db:
        jobs_repo.create_job(db, job_id, "clean", "uploads/x.csv")

    jobs_repo.set_status(job_id, JobStatus.PROCESSING, session_factory=session_factory)
    jobs_repo.set_status(
        job_id,
        JobStatus.COMPLETED,
        output_file_path="results/x.csv",
        session_factory=session_factory,
    )

    with session_factory() as db:
        job = jobs_repo.get_job(db, job_id)
    assert job is not None
    assert job.status == "COMPLETED"
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.output_file_path == "results/x.csv"


def test_deleting_schema_keeps_its_jobs(session_factory):
    job_id = uuid4()
    with session_factory() as db:
        schema = SchemaModel(name=f"tmp-{job_id}", definition={"fields": {}})
        db.add(schema)
        db.commit()
        db.add(JobModel(job_id=job_id, operation_type="validate", schema_id=schema.schema_id))
        db.commit()
        # Raw SQL so the database rule (not the ORM) is what gets tested.
        db.execute(text("DELETE FROM schemas WHERE schema_id = :id"), {"id": schema.schema_id})
        db.commit()

    with session_factory() as db:
        job = db.get(JobModel, job_id)
    assert job is not None
    assert job.schema_id is None
