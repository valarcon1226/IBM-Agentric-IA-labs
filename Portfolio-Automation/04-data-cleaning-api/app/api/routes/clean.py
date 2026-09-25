import io
import json
import logging
import uuid

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.services.cleaner import clean_dataframe
from app.services.storage import upload_file
from app.services.tasks import process_clean_job

logger = logging.getLogger(__name__)
router = APIRouter()
MAX_SYNC_BYTES = settings.MAX_SYNC_SIZE_MB * 1024 * 1024
PARSE_ERRORS = (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError)


@router.post("/clean")
async def clean_data(file: UploadFile = File(...), options: str = Form(...)):
    try:
        options_dict = json.loads(options)
    except json.JSONDecodeError as e:
        raise HTTPException(400, "Invalid options JSON") from e

    file_bytes = await file.read()
    if len(file_bytes) < MAX_SYNC_BYTES:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
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
    else:
        job_id = str(uuid.uuid4())
        try:
            obj_key = upload_file(file_bytes, f"raw_{job_id}_{file.filename}")
            process_clean_job.delay(job_id, obj_key, options_dict)
            return {"status": "processing", "job_id": job_id}
        except Exception as e:
            logger.exception("Could not enqueue clean job %s", job_id)
            raise HTTPException(500, "Internal processing error") from e
