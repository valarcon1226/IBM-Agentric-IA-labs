import logging
from typing import Any

import pandas as pd
import pandera as pa
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ValidateRequest(BaseModel):
    schema_id: str
    data: list[dict[str, Any]]


MOCK_SCHEMAS = {
    "user_schema": pa.DataFrameSchema(
        {"id": pa.Column(int), "name": pa.Column(str), "age": pa.Column(int, checks=pa.Check.ge(0))}
    )
}


@router.post("/validate")
async def validate_data(request: ValidateRequest):
    schema = MOCK_SCHEMAS.get(request.schema_id)
    if not schema:
        raise HTTPException(404, "Schema not found")
    try:
        schema.validate(pd.DataFrame(request.data), lazy=True)
        return {"status": "valid"}
    except pa.errors.SchemaErrors as err:
        return {"status": "invalid", "errors": err.failure_cases.to_dict(orient="records")}
    except Exception as e:
        logger.exception("Unhandled error in validate route")
        raise HTTPException(500, "Internal processing error") from e
