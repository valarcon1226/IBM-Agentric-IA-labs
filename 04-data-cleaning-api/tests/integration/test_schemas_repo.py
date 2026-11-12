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
