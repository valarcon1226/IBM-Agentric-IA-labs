from uuid import uuid4

from app.models.db import JobStatus
from app.services import jobs_repo, tasks


def _patch(monkeypatch, csv: bytes = b"A\n1\n1\n", fail_upload: bool = False) -> list:
    statuses: list = []
    monkeypatch.setattr(
        jobs_repo, "set_status", lambda jid, status, **kw: statuses.append((status, kw))
    )
    monkeypatch.setattr(tasks, "download_file", lambda key: csv)

    def fake_upload(content, name):
        if fail_upload:
            raise RuntimeError("minio down")
        return name

    monkeypatch.setattr(tasks, "upload_file", fake_upload)
    return statuses


def test_clean_task_marks_completed_with_output_path(monkeypatch):
    statuses = _patch(monkeypatch)
    job_id = str(uuid4())

    tasks.process_clean_job(job_id, "uploads/x.csv", {"remove_duplicates": True})

    assert [s for s, _ in statuses] == [JobStatus.PROCESSING, JobStatus.COMPLETED]
    assert statuses[-1][1]["output_file_path"] == f"results/cleaned_{job_id}.csv"


def test_clean_task_marks_failed_on_error(monkeypatch):
    statuses = _patch(monkeypatch, fail_upload=True)

    tasks.process_clean_job(str(uuid4()), "uploads/x.csv", {})

    assert [s for s, _ in statuses] == [JobStatus.PROCESSING, JobStatus.FAILED]
    assert "RuntimeError" in statuses[-1][1]["error_message"]


def test_transform_task_rejects_unknown_operation(monkeypatch):
    statuses = _patch(monkeypatch)

    tasks.process_transform_job(str(uuid4()), "uploads/x.csv", {"type": "nope", "args": {}})

    assert [s for s, _ in statuses] == [JobStatus.PROCESSING, JobStatus.FAILED]
    assert "Unknown transform" in statuses[-1][1]["error_message"]
