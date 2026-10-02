import json
from typing import Any

from sqlalchemy import text

from app.database import get_engine

# DECISIONES-02 E7: a row is a hit only while it is fresher than 30 days; otherwise this
# query returns nothing and the caller treats it exactly like a cache miss.
_READ_SQL = text(
    "SELECT company_name, status, incorporation_date, raw_data "
    "FROM company_cache "
    "WHERE country_code = :country_code AND company_identifier = :identifier "
    "AND last_updated > NOW() - INTERVAL '30 days'"
)

_UPSERT_SQL = text(
    "INSERT INTO company_cache "
    "(country_code, company_identifier, company_name, status, incorporation_date, raw_data, "
    "last_updated) "
    "VALUES (:country_code, :identifier, :company_name, :status, :incorporation_date, "
    "CAST(:raw_data AS jsonb), NOW()) "
    "ON CONFLICT (country_code, company_identifier) DO UPDATE SET "
    "company_name = EXCLUDED.company_name, "
    "status = EXCLUDED.status, "
    "incorporation_date = EXCLUDED.incorporation_date, "
    "raw_data = EXCLUDED.raw_data, "
    "last_updated = NOW()"
)


async def read_cache(country_code: str, identifier: str) -> dict[str, Any] | None:
    """Return the cached lookup for (country_code, identifier) if it is still fresh (<30 days).

    Returns None on a miss (no row, or a row older than 30 days) — the caller cannot and does
    not need to tell the two cases apart.
    """
    async with get_engine().connect() as connection:
        result = await connection.execute(
            _READ_SQL, {"country_code": country_code, "identifier": identifier}
        )
        row = result.mappings().first()
    return dict(row) if row is not None else None


async def upsert_cache(country_code: str, identifier: str, data: dict[str, Any]) -> None:
    """Insert or refresh the cached lookup for (country_code, identifier).

    Only ever called with a successful lookup (DECISIONES-02 E7): errors and "not found"
    results from a registry are never cached.
    """
    async with get_engine().begin() as connection:
        await connection.execute(
            _UPSERT_SQL,
            {
                "country_code": country_code,
                "identifier": identifier,
                "company_name": data.get("company_name"),
                "status": data.get("status"),
                "incorporation_date": data.get("incorporation_date"),
                "raw_data": json.dumps(data.get("raw_data")),
            },
        )
