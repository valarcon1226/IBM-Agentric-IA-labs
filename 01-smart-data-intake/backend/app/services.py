import csv
import io
import json
import logging
import re
from typing import Literal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text

from app import db
from app.config import settings
from app.models import ReviewItem, RowData

EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
PHONE = re.compile(r"\+?[\d\s\-().]{7,}")


def normalize_row(row: dict) -> dict:
    result = {key: str(value or "").strip() for key, value in row.items()}
    result["email"] = result.get("email", "").lower()
    return result


def row_issues(row: dict) -> list[str]:
    data = normalize_row(row)
    issues = []
    if not data.get("first_name") or not data.get("last_name"):
        issues.append("Missing required fields")
    if not EMAIL.fullmatch(data.get("email", "")):
        issues.append("Invalid email")
    if not data.get("company"):
        issues.append("Missing company")
    if EMAIL.fullmatch(data.get("email", "")) and "." not in data["email"].split("@")[1]:
        issues.append("Potentially invalid email domain")
    if not PHONE.fullmatch(data.get("phone", "")):
        issues.append("Invalid phone")
    return issues


def clean_row(row: dict) -> Literal["clean", "ambiguous", "failed"]:
    issues = row_issues(row)
    if "Missing required fields" in issues or "Invalid email" in issues:
        return "failed"
    return "ambiguous" if issues else "clean"


def is_allowed_callback_url(callback_url: str, base_url: str | None) -> bool:
    if not base_url or not callback_url or callback_url != callback_url.strip():
        return False
    try:
        base = urlsplit(base_url)
        candidate = urlsplit(callback_url)
        same_origin = (
            candidate.scheme.lower() == base.scheme.lower()
            and candidate.hostname is not None
            and candidate.hostname.lower() == (base.hostname or "").lower()
            and candidate.port == base.port
            and candidate.username is None
            and candidate.password is None
        )
    except ValueError:
        return False
    if not same_origin or base.query or base.fragment or candidate.fragment:
        return False
    base_path = unquote(base.path)
    callback_path = unquote(candidate.path)
    if not base_path.endswith("/"):
        base_path += "/"
    if not callback_path.startswith(base_path):
        return False
    return not any(part in {".", ".."} for part in callback_path.split("/"))


def process_upload(upload_id: UUID, callback_url: str | None = None) -> None:
    try:
        stored = db.get_minio().get_object(settings.MINIO_BUCKET_NAME, str(upload_id))
        try:
            rows = list(csv.DictReader(io.StringIO(stored.read().decode("utf-8-sig"))))
        finally:
            stored.close()
            stored.release_conn()
        for line_number, raw in enumerate(rows, start=2):
            row = normalize_row(raw)
            classification = clean_row(row)
            if classification == "ambiguous":
                item = ReviewItem(
                    record_id=uuid4(),
                    upload_id=upload_id,
                    line_number=line_number,
                    data=RowData.model_validate(row),
                    reasons=row_issues(row),
                )
                db.get_redis().lpush("review_queue", item.model_dump_json())
                continue
            if classification == "failed":
                log_error(upload_id, line_number, row, "; ".join(row_issues(row)))
                continue
            if not insert_clean(upload_id, line_number, row):
                log_error(upload_id, line_number, row, "Duplicate email in upload")
        with db.get_engine().begin() as connection:
            connection.execute(
                text(
                    "UPDATE uploads SET status='completed', total_rows=:total "
                    "WHERE upload_id=CAST(:id AS uuid)"
                ),
                {"id": str(upload_id), "total": len(rows)},
            )
        callback_target = callback_url if callback_url is not None else settings.N8N_CALLBACK_URL
        if callback_target:
            try:
                if callback_url is not None and not is_allowed_callback_url(
                    callback_url, settings.N8N_RESUME_BASE_URL
                ):
                    raise ValueError("Unvalidated n8n callback URL")
                from app.routes import get_status

                status = get_status(upload_id)
                payload = status.model_dump(mode="json")
                payload["clean_rows_count"] = payload.pop("clean_rows")
                with db.get_engine().connect() as connection:
                    result = connection.execute(
                        text(
                            "SELECT line_number, first_name, last_name, email, phone, company "
                            "FROM clean_data WHERE upload_id=CAST(:id AS uuid) "
                            "ORDER BY line_number"
                        ),
                        {"id": str(upload_id)},
                    )
                    payload["clean_rows"] = [dict(row) for row in result.mappings().all()]
                httpx.post(callback_target, json=payload, timeout=5).raise_for_status()
            except Exception:
                logging.exception("Intake callback failed for %s", upload_id)
    except Exception:
        logging.exception("Intake processing failed for %s", upload_id)
        with db.get_engine().begin() as connection:
            connection.execute(
                text("UPDATE uploads SET status='failed' WHERE upload_id=CAST(:id AS uuid)"),
                {"id": str(upload_id)},
            )


def insert_clean(upload_id: UUID, line_number: int, row: dict) -> bool:
    with db.get_engine().begin() as connection:
        inserted = connection.execute(
            text(
                "INSERT INTO clean_data (upload_id, line_number, first_name, last_name, email, "
                "phone, company) "
                "VALUES (CAST(:id AS uuid), :line, :first_name, :last_name, :email, "
                ":phone, :company) "
                "ON CONFLICT (upload_id, email) DO NOTHING RETURNING record_id"
            ),
            {"id": str(upload_id), "line": line_number, **row},
        )
        return inserted.scalar_one_or_none() is not None


def log_error(upload_id: UUID, line_number: int, row: dict, reason: str) -> None:
    with db.get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO error_log (upload_id, line_number, row_data, error_reason) "
                "VALUES (CAST(:id AS uuid), :line, CAST(:row AS jsonb), :reason)"
            ),
            {"id": str(upload_id), "line": line_number, "row": json.dumps(row), "reason": reason},
        )
