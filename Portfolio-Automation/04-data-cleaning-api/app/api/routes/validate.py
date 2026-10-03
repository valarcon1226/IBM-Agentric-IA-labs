import logging
from typing import Any
from uuid import UUID

import pandas as pd
import pandera as pa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import schemas_repo

logger = logging.getLogger(__name__)
router = APIRouter()


class ValidateRequest(BaseModel):
    schema_id: str
    data: list[dict[str, Any]]


BUILTIN_SCHEMAS = {
    "user_schema": pa.DataFrameSchema(
        {"id": pa.Column(int), "name": pa.Column(str), "age": pa.Column(int, checks=pa.Check.ge(0))}
    )
}


def _resolve_schema(schema_id: str, db: Session) -> pa.DataFrameSchema | None:
    if schema_id in BUILTIN_SCHEMAS:
        return BUILTIN_SCHEMAS[schema_id]
    try:
        uid = UUID(schema_id)
    except ValueError:
        return None
    stored = schemas_repo.get_schema(db, uid)
    return None if stored is None else schemas_repo.to_pandera(stored.definition)


@router.post("/validate")
def validate_data(request: ValidateRequest, db: Session = Depends(get_db)):
    schema = _resolve_schema(request.schema_id, db)
    if schema is None:
        raise HTTPException(404, "Schema not found")
    try:
        schema.validate(pd.DataFrame(request.data), lazy=True)
        return {"status": "valid"}
    except pa.errors.SchemaErrors as err:
        return {"status": "invalid", "errors": err.failure_cases.to_dict(orient="records")}
    except Exception as e:
        logger.exception("Unhandled error in validate route")
        raise HTTPException(500, "Internal processing error") from e
