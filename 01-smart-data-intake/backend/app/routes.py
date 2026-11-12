from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy import text

from app import db
from app.config import settings
from app.models import (
    ReviewItem,
    ReviewRequest,
    ReviewResponse,
    ReviewResult,
    StatusResponse,
    UploadResponse,
)
from app.security import verify_api_key
from app.services import insert_clean, is_allowed_callback_url, log_error, process_upload

router = APIRouter(prefix="/api/v1/intake", dependencies=[Depends(verify_api_key)])


@router.post("/upload", response_model=UploadResponse, status_code=202)
def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    callback_url: str | None = Form(default=None),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv") or len(file.filename) > 255:
        raise HTTPException(status_code=400, detail="A CSV filename is required")
    if callback_url is not None and not is_allowed_callback_url(
        callback_url, settings.N8N_RESUME_BASE_URL
    ):
        raise HTTPException(status_code=400, detail="callback_url is not an allowed n8n resume URL")
    upload_id = uuid4()
    store = db.get_minio()
    if not store.bucket_exists(settings.MINIO_BUCKET_NAME):
        store.make_bucket(settings.MINIO_BUCKET_NAME)
    file.file.seek(0, 2)
    length = file.file.tell()
    file.file.seek(0)
    store.put_object(settings.MINIO_BUCKET_NAME, str(upload_id), file.file, length)
    with db.get_engine().begin() as connection:
        connection.execute(
            text("INSERT INTO uploads (upload_id, filename) VALUES (:id, :filename)"),
            {"id": str(upload_id), "filename": file.filename},
        )
    background_tasks.add_task(process_upload, upload_id, callback_url)
    return UploadResponse(
        upload_id=upload_id, status="processing", message="File received and validation started."
    )


def pending_items(upload_id: UUID) -> list[tuple[str, ReviewItem]]:
    return [
        (raw.decode() if isinstance(raw, bytes) else raw, item)
        for raw in db.get_redis().lrange("review_queue", 0, -1)
        if (item := ReviewItem.model_validate_json(raw)).upload_id == upload_id
    ]


@router.get("/{upload_id}", response_model=StatusResponse)
def get_status(upload_id: UUID) -> StatusResponse:
    with db.get_engine().connect() as connection:
        upload = connection.execute(
            text("SELECT status, total_rows FROM uploads WHERE upload_id=CAST(:id AS uuid)"),
            {"id": str(upload_id)},
        ).first()
        if upload is None:
            raise HTTPException(status_code=404, detail="Upload not found")
        clean = connection.execute(
            text("SELECT COUNT(*) FROM clean_data WHERE upload_id=CAST(:id AS uuid)"),
            {"id": str(upload_id)},
        ).scalar_one()
        failed = connection.execute(
            text("SELECT COUNT(*) FROM error_log WHERE upload_id=CAST(:id AS uuid)"),
            {"id": str(upload_id)},
        ).scalar_one()
    return StatusResponse(
        upload_id=upload_id,
        status=upload.status,
        total_rows=upload.total_rows,
        clean_rows=clean,
        ambiguous_rows=len(pending_items(upload_id)),
        failed_rows=failed,
    )


@router.get("/{upload_id}/review", response_model=ReviewResponse)
def get_review(upload_id: UUID) -> ReviewResponse:
    return ReviewResponse(
        upload_id=upload_id, pending_reviews=[item for _, item in pending_items(upload_id)]
    )


@router.post("/{upload_id}/review", response_model=ReviewResult)
def review(upload_id: UUID, request: ReviewRequest) -> ReviewResult:
    match = next(
        (
            (raw, item)
            for raw, item in pending_items(upload_id)
            if item.record_id == request.record_id
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Review record not found")
    raw, item = match
    if request.action == "approve":
        row = (request.corrected_data or item.data).model_dump()
        if not insert_clean(upload_id, item.line_number, row):
            log_error(upload_id, item.line_number, row, "Duplicate email in upload")
        message = "Record approved and moved to clean_data"
    else:
        log_error(upload_id, item.line_number, item.data.model_dump(), "Rejected in review")
        message = "Record rejected and moved to error_log"
    db.get_redis().lrem("review_queue", 1, raw)
    return ReviewResult(status="success", message=message)
