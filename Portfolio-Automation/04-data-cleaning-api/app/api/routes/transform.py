import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.tasks import process_transform_job

logger = logging.getLogger(__name__)
router = APIRouter()


class TransformRequest(BaseModel):
    file_path: str
    operation: str
    params: dict[str, Any]


@router.post("/transform")
async def transform_data(request: TransformRequest):
    job_id = str(uuid.uuid4())
    try:
        process_transform_job.delay(
            job_id, request.file_path, {"type": request.operation, "args": request.params}
        )
        return {"status": "processing", "job_id": job_id}
    except Exception as e:
        logger.exception("Unhandled error in transform route")
        raise HTTPException(500, "Internal processing error") from e
