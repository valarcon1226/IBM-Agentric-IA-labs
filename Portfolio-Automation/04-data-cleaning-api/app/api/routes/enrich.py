import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.tasks import process_enrich_job

logger = logging.getLogger(__name__)
router = APIRouter()


class EnrichRequest(BaseModel):
    file_path: str
    operations: list[str]
    target_columns: dict[str, str]


@router.post("/enrich")
async def enrich_data(request: EnrichRequest):
    job_id = str(uuid.uuid4())
    try:
        process_enrich_job.delay(
            job_id, request.file_path, request.operations, request.target_columns
        )
        return {"status": "processing", "job_id": job_id}
    except Exception as e:
        logger.exception("Unhandled error in enrich route")
        raise HTTPException(500, "Internal processing error") from e
