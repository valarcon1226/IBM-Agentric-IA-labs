import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SchemaDef(BaseModel):
    name: str
    fields: dict[str, str]


DB: list[dict[str, Any]] = []


@router.post("/schemas")
async def create_schema(s: SchemaDef):
    sid = f"sch_{uuid.uuid4().hex[:8]}"
    doc = {"id": sid, "name": s.name, "fields": s.fields}
    DB.append(doc)
    return {"status": "success", "schema_id": sid, "data": doc}


@router.get("/schemas")
async def list_schemas():
    return {"status": "success", "schemas": DB}
