from app.models.db import JobModel, JobStatus


def test_job_status_values_match_sql():
    assert [s.value for s in JobStatus] == ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


def test_job_schema_fk_sets_null_on_delete():
    (fk,) = JobModel.__table__.c.schema_id.foreign_keys
    assert fk.ondelete == "SET NULL"
