import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import jobs_repo
from app.services.tasks import process_enrich_job

logger = logging.getLogger(__name__)
router = APIRouter()


class EnrichRequest(BaseModel):
    file_path: str
    operations: list[str]
    target_columns: dict[str, str]


@router.post("/enrich")
def enrich_data(request: EnrichRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4()
    jobs_repo.create_job(db, job_id, "enrich", request.file_path)
    try:
        process_enrich_job.delay(
            str(job_id), request.file_path, request.operations, request.target_columns
        )
    except Exception as e:
        logger.exception("Could not enqueue enrich job %s", job_id)
        jobs_repo.mark_enqueue_failed(job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"status": "processing", "job_id": str(job_id)}
