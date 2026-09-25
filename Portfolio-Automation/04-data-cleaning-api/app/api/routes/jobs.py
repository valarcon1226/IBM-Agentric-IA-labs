import logging

from fastapi import APIRouter, HTTPException

from app.services.storage import generate_presigned_url

logger = logging.getLogger(__name__)
router = APIRouter()

MOCK_JOBS = {"job_1": {"status": "COMPLETED", "result_key": "res.csv"}}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    return {"job_id": job_id, **MOCK_JOBS.get(job_id, {"status": "UNKNOWN"})}


@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    job = MOCK_JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "COMPLETED":
        raise HTTPException(400, "Job not completed")
    try:
        return {
            "job_id": job_id,
            "download_url": generate_presigned_url(job["result_key"]),
        }
    except Exception as e:
        logger.exception("Unhandled error in jobs route")
        raise HTTPException(500, "Internal processing error") from e
