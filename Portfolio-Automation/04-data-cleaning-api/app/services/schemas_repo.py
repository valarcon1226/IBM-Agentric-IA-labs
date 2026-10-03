"""Persistence and Pandera conversion for user-defined validation schemas."""

from typing import Any
from uuid import UUID

import pandera as pa
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.db import SchemaModel

# Public field types accepted by POST /schemas -> Pandera dtype.
ALLOWED_TYPES: dict[str, Any] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "datetime": "datetime64[ns]",
}


class DuplicateSchemaError(Exception):
    """A schema with this name already exists."""


def create_schema(db: Session, name: str, fields: dict[str, str]) -> SchemaModel:
    schema = SchemaModel(name=name, definition={"fields": fields})
    db.add(schema)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise DuplicateSchemaError(name) from e
    db.refresh(schema)
    return schema


def list_schemas(db: Session) -> list[SchemaModel]:
    return list(db.scalars(select(SchemaModel).order_by(SchemaModel.created_at)))


def get_schema(db: Session, schema_id: UUID) -> SchemaModel | None:
    return db.get(SchemaModel, schema_id)


def to_pandera(definition: dict[str, Any]) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {column: pa.Column(ALLOWED_TYPES[t]) for column, t in definition["fields"].items()}
    )
