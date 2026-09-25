# T07 — Schemas guardados en Postgres y usables en `/validate` (proyecto 04)

**Objetivo:**
- `POST /api/v1/schemas` guarda en la tabla `schemas`. El nombre repetido da 409 y un tipo no
  permitido da 422.
- `GET /api/v1/schemas` lee de la tabla.
- `POST /api/v1/validate` acepta el schema incorporado `user_schema` **o** el UUID de un schema
  guardado.
- Se elimina la lista `DB` en memoria.

**Archivos que puedes tocar:**
- `04-data-cleaning-api/app/services/schemas_repo.py` (nuevo)
- `04-data-cleaning-api/app/api/routes/schemas.py`
- `04-data-cleaning-api/app/api/routes/validate.py`
- `04-data-cleaning-api/tests/test_api.py`
- `04-data-cleaning-api/tests/integration/test_schemas_repo.py` (nuevo)

## Antes de empezar

- `T06` en `DONE`. Compuertas → **38 passed, 2 deselected**.

## Paso 1 — `app/services/schemas_repo.py` (nuevo)

EXACTO:

```python
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
```

## Paso 2 — `app/api/routes/schemas.py` (reemplazo completo)

EXACTO:

```python
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
```

## Paso 3 — `app/api/routes/validate.py` (reemplazo completo)

EXACTO:

```python
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
```

## Paso 4 — `tests/test_api.py`

4a. En la línea `from app.services import jobs_repo, storage` agrega `schemas_repo`:
`from app.services import jobs_repo, schemas_repo, storage`.

4b. Reemplaza **las dos** funciones existentes `test_create_schema` y `test_list_schemas`
(completas) por. EXACTO:

```python
def test_create_schema(monkeypatch, fake_db):
    monkeypatch.setattr(
        schemas_repo,
        "create_schema",
        lambda db, name, fields: SimpleNamespace(
            schema_id=uuid4(), name=name, definition={"fields": fields}
        ),
    )
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "int"}})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["data"]["fields"] == {"id": "int"}


def test_list_schemas(monkeypatch, fake_db):
    monkeypatch.setattr(schemas_repo, "list_schemas", lambda db: [])
    res = client.get("/api/v1/schemas")
    assert res.status_code == 200
    assert res.json() == {"status": "success", "schemas": []}
```

**Importante:** estas funciones usan el fixture `fake_db`, que está definido más abajo en el
mismo archivo (lo agregó T05). pytest lo resuelve igual; no lo muevas.

4c. Al final del archivo agrega. EXACTO:

```python


def test_created_schema_is_usable_in_validate(monkeypatch, fake_db):
    sid = uuid4()
    stored = SimpleNamespace(
        schema_id=sid, name="customers", definition={"fields": {"id": "int", "email": "str"}}
    )
    monkeypatch.setattr(
        schemas_repo, "get_schema", lambda db, schema_id: stored if schema_id == sid else None
    )

    ok = client.post(
        "/api/v1/validate",
        json={"schema_id": str(sid), "data": [{"id": 1, "email": "a@b.co"}]},
    )
    bad = client.post(
        "/api/v1/validate",
        json={"schema_id": str(sid), "data": [{"id": "x", "email": "a@b.co"}]},
    )

    assert ok.json()["status"] == "valid"
    assert bad.json()["status"] == "invalid"


def test_create_schema_rejects_unknown_type(fake_db):
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "uuid"}})
    assert res.status_code == 422


def test_create_schema_duplicate_name_returns_409(monkeypatch, fake_db):
    def duplicate(db, name, fields):
        raise schemas_repo.DuplicateSchemaError(name)

    monkeypatch.setattr(schemas_repo, "create_schema", duplicate)
    res = client.post("/api/v1/schemas", json={"name": "A", "fields": {"id": "int"}})
    assert res.status_code == 409
```

## Paso 5 — `tests/integration/test_schemas_repo.py` (nuevo)

EXACTO:

```python
import pytest

from app.services import schemas_repo

pytestmark = pytest.mark.integration


def test_schema_persists_and_duplicate_is_rejected(session_factory):
    with session_factory() as db:
        created = schemas_repo.create_schema(db, "customers-it", {"id": "int"})

    with session_factory() as db:
        stored = schemas_repo.get_schema(db, created.schema_id)
        assert stored is not None
        assert stored.definition == {"fields": {"id": "int"}}
        with pytest.raises(schemas_repo.DuplicateSchemaError):
            schemas_repo.create_schema(db, "customers-it", {"id": "int"})
```

## Verificación

1. Compuertas → **41 passed, 3 deselected**, ruff y mypy limpios.
2. Integración (ver T06, Verificación 2) → **3 passed** o **3 skipped** explicado.
3. `Select-String -Path app -Recurse -Pattern "MOCK_SCHEMAS|^DB: list"` → **sin coincidencias**.

## Terminado cuando

Todas pasan. Reporta y marca `T07` como `DONE`.
