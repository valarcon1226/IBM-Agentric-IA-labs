import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import jobs_repo
from app.services.tasks import process_transform_job

logger = logging.getLogger(__name__)
router = APIRouter()


class TransformRequest(BaseModel):
    file_path: str
    operation: str
    params: dict[str, Any]


@router.post("/transform")
def transform_data(request: TransformRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4()
    jobs_repo.create_job(db, job_id, "transform", request.file_path)
    try:
        process_transform_job.delay(
            str(job_id), request.file_path, {"type": request.operation, "args": request.params}
        )
    except Exception as e:
        logger.exception("Could not enqueue transform job %s", job_id)
        jobs_repo.mark_enqueue_failed(job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"status": "processing", "job_id": str(job_id)}
