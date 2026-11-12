import logging
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.storage import upload_file

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        obj_key = f"uploads/{uuid.uuid4()}_{file.filename}"
        upload_file(file_bytes, obj_key)
        return {"status": "success", "file_url": obj_key, "size": len(file_bytes)}
    except Exception as e:
        logger.exception("Unhandled error in upload route")
        raise HTTPException(500, "Internal processing error") from e
