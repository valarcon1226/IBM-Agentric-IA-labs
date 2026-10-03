"""Async data access for the `/api/v1/notify*` endpoints (DECISIONES-03 N8).

Same pattern as `02-business-registry-enricher/app/cache.py`: SQLAlchemy's async engine +
parameterized `text()` queries, no ORM.
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.database import get_engine

_INSERT_SQL = text(
    "INSERT INTO notifications (template_name, priority, recipients, payload) "
    "VALUES (:template_name, :priority, CAST(:recipients AS jsonb), CAST(:payload AS jsonb)) "
    "RETURNING id, status, created_at"
)

_SELECT_NOTIFICATION_SQL = text(
    "SELECT id, template_name, status, created_at FROM notifications WHERE id = :id"
)

_SELECT_LOGS_SQL = text(
    "SELECT channel, status, processed_at FROM delivery_logs "
    "WHERE notification_id = :id ORDER BY processed_at"
)


async def insert_notification(
    template_name: str,
    priority: str,
    recipients: dict[str, list[str]],
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    async with get_engine().begin() as connection:
        result = await connection.execute(
            _INSERT_SQL,
            {
                "template_name": template_name,
                "priority": priority,
                "recipients": json.dumps(recipients),
                "payload": json.dumps(payload) if payload is not None else None,
            },
        )
        row = result.mappings().one()
    return {"id": str(row["id"]), "status": row["status"], "created_at": row["created_at"]}


async def get_notification(notification_id: str) -> dict[str, Any] | None:
    async with get_engine().connect() as connection:
        result = await connection.execute(_SELECT_NOTIFICATION_SQL, {"id": notification_id})
        row = result.mappings().first()
        if row is None:
            return None
        logs_result = await connection.execute(_SELECT_LOGS_SQL, {"id": notification_id})
        delivery_logs = [dict(log_row) for log_row in logs_result.mappings().all()]

    data = dict(row)
    data["id"] = str(data["id"])
    data["delivery_logs"] = delivery_logs
    return data


async def list_notifications(
    status: str | None, since: datetime | None, limit: int
) -> tuple[list[dict[str, Any]], int]:
    conditions = []
    params: dict[str, Any] = {}
    if status is not None:
        conditions.append("status = :status")
        params["status"] = status
    if since is not None:
        conditions.append("created_at >= :since")
        params["since"] = since
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    list_query = text(
        "SELECT id, template_name, status, created_at FROM notifications "
        f"{where_clause} ORDER BY created_at DESC LIMIT :limit"
    )
    count_query = text(f"SELECT COUNT(*) FROM notifications {where_clause}")

    async with get_engine().connect() as connection:
        result = await connection.execute(list_query, {**params, "limit": limit})
        rows = [dict(row) for row in result.mappings().all()]
        count_result = await connection.execute(count_query, params)
        total: int = count_result.scalar_one()

    for row in rows:
        row["id"] = str(row["id"])
    return rows, total
