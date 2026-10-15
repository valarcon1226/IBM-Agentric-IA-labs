"""Celery application and asynchronous processing tasks."""

import base64
import logging
import uuid
from datetime import UTC, datetime

from celery import Celery

from app.core.config import settings
from app.core.ocr_engine import ocr_engine
from app.models.database import Invoice, LineItem, SessionLocal
from app.services.extractor import extractor
from app.services.storage import storage_service
from app.services.validator import validator

logger = logging.getLogger(__name__)

celery_app = Celery(
    "invoice_processor",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(bind=True, name="process_invoice_task")
def process_invoice_task(self, file_b64: str, filename: str) -> dict:
    """Asynchronously processes multi-page invoice: OCR -> MinIO -> Extract -> Validate -> DB."""
    try:
        self.update_state(
            state="PROCESSING",
            meta={"progress": "10%", "message": "Decoding invoice file"},
        )
        file_bytes = base64.b64decode(file_b64)

        self.update_state(
            state="PROCESSING",
            meta={"progress": "30%", "message": "Running OCR engine across pages"},
        )
        raw_text, page_count = ocr_engine.process_file(file_bytes, filename)

        self.update_state(
            state="PROCESSING",
            meta={"progress": "60%", "message": "Storing original and sidecar in MinIO"},
        )
        now_str = datetime.now(UTC).strftime("%Y/%m")
        unique_prefix = uuid.uuid4().hex[:8]
        minio_key = f"invoices/{now_str}/{unique_prefix}_{filename}"
        storage_service.upload_file(minio_key, file_bytes)

        sidecar_key = f"{minio_key}.ocr.txt"
        storage_service.upload_text(sidecar_key, raw_text)

        self.update_state(
            state="PROCESSING",
            meta={"progress": "80%", "message": "Extracting fields and validating rules"},
        )
        extracted = extractor.extract(raw_text)
        is_valid, validation_errors = validator.validate(extracted)

        # Save to database
        db = SessionLocal()
        try:
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
                line_item_record = LineItem(
                    invoice_id=invoice_record.invoice_id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
                db.add(line_item_record)

            db.commit()
            db.refresh(invoice_record)
            inv_id_str = str(invoice_record.invoice_id)
        finally:
            db.close()

        return {
            "status": "COMPLETED",
            "progress": "100%",
            "message": f"Successfully processed {page_count} pages",
            "invoice_id": inv_id_str,
            "is_valid": is_valid,
            "validation_errors": validation_errors,
        }

    except Exception as exc:
        logger.exception("Async invoice processing failed: %s", exc)
        return {
            "status": "FAILED",
            "progress": "0%",
            "message": str(exc),
            "invoice_id": None,
            "is_valid": False,
            "validation_errors": [f"Processing error: {exc}"],
        }
