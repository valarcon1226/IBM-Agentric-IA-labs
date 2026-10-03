from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import schemas_repo

router = APIRouter()

FieldType = Literal["int", "float", "str", "bool", "datetime"]


class SchemaDef(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    fields: dict[str, FieldType] = Field(min_length=1)


def _serialize(schema: Any) -> dict[str, Any]:
    return {
        "id": str(schema.schema_id),
        "name": schema.name,
        "fields": schema.definition["fields"],
    }


@router.post("/schemas")
def create_schema(s: SchemaDef, db: Session = Depends(get_db)):
    try:
        schema = schemas_repo.create_schema(db, s.name, dict(s.fields))
    except schemas_repo.DuplicateSchemaError as e:
        raise HTTPException(409, "Schema name already exists") from e
    data = _serialize(schema)
    return {"status": "success", "schema_id": data["id"], "data": data}


@router.get("/schemas")
def list_schemas(db: Session = Depends(get_db)):
    return {"status": "success", "schemas": [_serialize(s) for s in schemas_repo.list_schemas(db)]}
