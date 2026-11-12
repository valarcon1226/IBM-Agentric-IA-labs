import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services import jobs_repo
from app.services.cleaner import clean_dataframe
from app.services.readers import PARSE_ERRORS, SUPPORTED_EXTENSIONS, is_supported, read_table
from app.services.storage import upload_file
from app.services.tasks import process_clean_job

logger = logging.getLogger(__name__)
router = APIRouter()
MAX_SYNC_BYTES = settings.MAX_SYNC_SIZE_MB * 1024 * 1024


@router.post("/clean")
async def clean_data(
    file: UploadFile = File(...),
    options: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        options_dict = json.loads(options)
    except json.JSONDecodeError as e:
        raise HTTPException(400, "Invalid options JSON") from e

    file_bytes = await file.read()
    filename = file.filename or ""
    if not is_supported(filename):
        raise HTTPException(415, f"Unsupported file type. Use one of: {SUPPORTED_EXTENSIONS}")
    if len(file_bytes) < MAX_SYNC_BYTES:
        try:
            df = read_table(file_bytes, filename)
        except PARSE_ERRORS as e:
            raise HTTPException(400, f"Could not parse file: {type(e).__name__}") from e
        try:
            return {
                "status": "success",
                "data": clean_dataframe(df, options_dict).to_dict(orient="records"),
            }
        except Exception as e:
            logger.exception("Synchronous cleaning failed")
            raise HTTPException(500, "Internal processing error") from e

    job_id = uuid.uuid4()
    try:
        obj_key = upload_file(file_bytes, f"raw_{job_id}_{filename}")
    except Exception as e:
        logger.exception("Could not store upload for job %s", job_id)
        raise HTTPException(500, "Internal processing error") from e
    jobs_repo.create_job(db, job_id, "clean", obj_key)
    try:
        process_clean_job.delay(str(job_id), obj_key, options_dict)
    except Exception as e:
        logger.exception("Could not enqueue clean job %s", job_id)
        jobs_repo.mark_enqueue_failed(job_id)
        raise HTTPException(500, "Internal processing error") from e
    return {"status": "processing", "job_id": str(job_id)}
