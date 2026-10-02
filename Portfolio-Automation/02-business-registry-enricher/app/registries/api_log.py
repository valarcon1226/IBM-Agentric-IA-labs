import logging

from sqlalchemy import text

from app.database import get_engine

logger = logging.getLogger(__name__)


async def log_api_call(
    *,
    registry_name: str,
    endpoint: str,
    company_identifier: str,
    response_code: int | None,
    response_time_ms: int,
    error_message: str | None,
) -> None:
    """Insert one row into `api_logs`. A failure here is logged and never raised:
    a logging problem must not break a registry lookup that otherwise succeeded."""
    try:
        async with get_engine().begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO api_logs "
                    "(registry_name, endpoint, response_code, response_time_ms, "
                    "error_message, company_identifier) "
                    "VALUES (:registry_name, :endpoint, :response_code, :response_time_ms, "
                    ":error_message, :company_identifier)"
                ),
                {
                    "registry_name": registry_name,
                    "endpoint": endpoint,
                    "response_code": response_code,
                    "response_time_ms": response_time_ms,
                    "error_message": error_message,
                    "company_identifier": company_identifier,
                },
            )
    except Exception:
        logger.exception(
            "Failed to write api_logs row for registry=%s identifier=%s",
            registry_name,
            company_identifier,
        )
