"""FastAPI endpoints for invoice processing, retrieval, and export."""

import base64
import logging
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db, verify_bearer_token
from app.core.celery_app import celery_app, process_invoice_task
from app.core.config import settings
from app.core.ocr_engine import ocr_engine
from app.models.database import Invoice, LineItem
from app.models.schemas import (
    ExportRequest,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceResponse,
    JobResponse,
)
from app.services.exporter import exporter
from app.services.extractor import extractor
from app.services.storage import storage_service
from app.services.validator import validator

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    """Validates the upload (name, type, size) and returns a safe filename and its bytes."""
    filename = PurePath(file.filename or "invoice.pdf").name
    if PurePath(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de archivo no soportado. Usa: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado está vacío.",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera el límite de 10 MB.",
        )
    return filename, content


@router.post(
    "/api/v1/invoices/process",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_bearer_token)],
)
@router.post(
    "/invoices/process",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
async def process_invoice_sync(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """Synchronously processes a single invoice (PDF or image)."""
    filename, content = await _read_upload(file)
    pages = ocr_engine.count_pages(content, filename)
    if pages > settings.max_sync_pages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"La factura tiene {pages} páginas; el modo síncrono acepta hasta "
                f"{settings.max_sync_pages}. Usa /api/v1/invoices/upload."
            ),
        )

    # 1. OCR text extraction
    try:
        raw_text, _ = ocr_engine.process_file(content, filename)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo en motor OCR: {exc}",
        ) from exc

    # 2. Upload to MinIO
    now_str = datetime.now(UTC).strftime("%Y/%m")
    unique_prefix = uuid.uuid4().hex[:8]
    minio_key = f"invoices/{now_str}/{unique_prefix}_{filename}"
    try:
        storage_service.upload_file(minio_key, content)
        sidecar_key = f"{minio_key}.ocr.txt"
        storage_service.upload_text(sidecar_key, raw_text)
    except Exception:
        # The invoice data still matters without the original file; keep the key for a retry.
        logger.exception("Could not store %s in MinIO", minio_key)

    # 3. Extraction & Validation
    extracted = extractor.extract(raw_text)
    is_valid, validation_errors = validator.validate(extracted)

    # 4. Save to Database
    invoice_record = Invoice(
        original_filename=filename,
        minio_key=minio_key,
        issuer_name=extracted.issuer_name,
        issuer_vat=extracted.issuer_vat,
        recipient_name=extracted.recipient_name,
        recipient_vat=extracted.recipient_vat,
        invoice_number=extracted.invoice_number,
        invoice_date=extracted.invoice_date,
        due_date=extracted.due_date,
        subtotal=extracted.subtotal,
        tax_rate=extracted.tax_rate,
        tax_amount=extracted.tax_amount,
        total=extracted.total,
        currency=extracted.currency,
        is_valid=is_valid,
        validation_errors=validation_errors,
        status="COMPLETED",
    )
    db.add(invoice_record)
    db.flush()

    for item in extracted.line_items:
        line_item = LineItem(
            invoice_id=invoice_record.invoice_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        db.add(line_item)

    db.commit()
    db.refresh(invoice_record)

    # Query with line items loaded
    result = db.scalars(
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.invoice_id == invoice_record.invoice_id)
    ).first()

    return InvoiceResponse.model_validate(result)


@router.post(
    "/api/v1/invoices/upload",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_bearer_token)],
)
@router.post(
    "/invoices/upload",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
async def upload_invoice_async(
    file: UploadFile = File(...),
) -> JobResponse:
    """Uploads multi-page invoice for background asynchronous processing via Celery."""
    filename, content = await _read_upload(file)

    file_b64 = base64.b64encode(content).decode("utf-8")
    task = process_invoice_task.apply_async(args=[file_b64, filename])

    return JobResponse(
        job_id=task.id,
        status="PENDING",
        message="Invoice queued for asynchronous processing.",
    )


@router.get(
    "/api/v1/invoices/jobs/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(verify_bearer_token)],
)
@router.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
def get_job_status(job_id: str) -> JobResponse:
    """Checks the status of an asynchronous processing job."""
    task_result = AsyncResult(job_id, app=celery_app)
    state = task_result.state

    if state == "PENDING":
        return JobResponse(
            job_id=job_id,
            status="PENDING",
            progress="0%",
            message="Job waiting in queue",
        )
    if state == "PROCESSING":
        meta = task_result.info if isinstance(task_result.info, dict) else {}
        return JobResponse(
            job_id=job_id,
            status="PROCESSING",
            progress=meta.get("progress", "50%"),
            message=meta.get("message", "Processing invoice"),
        )
    if state == "SUCCESS":
        result = task_result.result if isinstance(task_result.result, dict) else {}
        inv_id = result.get("invoice_id")
        return JobResponse(
            job_id=job_id,
            status=result.get("status", "COMPLETED"),
            progress="100%",
            message=result.get("message", "Completed successfully"),
            invoice_id=uuid.UUID(inv_id) if inv_id else None,
        )
    if state == "FAILURE":
        return JobResponse(
            job_id=job_id,
            status="FAILED",
            progress="0%",
            message=str(task_result.result),
        )

    return JobResponse(
        job_id=job_id,
        status=state,
        message="Job in state " + state,
    )


@router.get(
    "/api/v1/invoices",
    response_model=InvoiceListResponse,
    dependencies=[Depends(verify_bearer_token)],
)
@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
def list_invoices(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> InvoiceListResponse:
    """Lists processed invoices with pagination."""
    offset = (page - 1) * limit
    total_records = db.query(Invoice).count()

    invoices = (
        db.query(Invoice).order_by(Invoice.created_at.desc()).offset(offset).limit(limit).all()
    )

    items = [
        InvoiceListItem(
            invoice_id=inv.invoice_id,
            issuer_name=inv.issuer_name,
            total=inv.total,
            currency=inv.currency,
            is_valid=inv.is_valid,
            status=inv.status,
            created_at=inv.created_at,
        )
        for inv in invoices
    ]

    return InvoiceListResponse(
        data=items,
        total_records=total_records,
        page=page,
        limit=limit,
    )


@router.get(
    "/api/v1/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[Depends(verify_bearer_token)],
)
@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
def get_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """Retrieves full details of a specific invoice."""
    invoice = db.scalars(
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.invoice_id == invoice_id)
    ).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factura con ID '{invoice_id}' no encontrada.",
        )

    return InvoiceResponse.model_validate(invoice)


@router.post(
    "/api/v1/invoices/export",
    dependencies=[Depends(verify_bearer_token)],
)
@router.post(
    "/invoices/export",
    dependencies=[Depends(verify_bearer_token)],
    include_in_schema=False,
)
def export_invoices(
    request: ExportRequest,
    db: Session = Depends(get_db),
):
    """Exports processed invoices to CSV format."""
    query = select(Invoice).order_by(Invoice.created_at.desc())
    if request.start_date:
        query = query.where(Invoice.invoice_date >= request.start_date)
    if request.end_date:
        query = query.where(Invoice.invoice_date <= request.end_date)

    invoices = db.scalars(query).all()
    csv_data = exporter.to_csv(invoices)

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices_export.csv"},
    )
