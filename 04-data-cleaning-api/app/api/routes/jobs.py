import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db import JobStatus
from app.models.domain import JobResponse
from app.services import jobs_repo
from app.services.storage import generate_presigned_url

logger = logging.getLogger(__name__)
router = APIRouter()

DOWNLOAD_URL_TTL_SECONDS = 3600


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: UUID, db: Session = Depends(get_db)):
    job = jobs_repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: UUID, db: Session = Depends(get_db)):
    job = jobs_repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.COMPLETED or not job.output_file_path:
        raise HTTPException(400, "Job not completed")
    try:
        url = generate_presigned_url(job.output_file_path, expires=DOWNLOAD_URL_TTL_SECONDS)
    except Exception as e:
        logger.exception("Could not presign result for job %s", job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"job_id": str(job_id), "download_url": url, "expires_in": DOWNLOAD_URL_TTL_SECONDS}
