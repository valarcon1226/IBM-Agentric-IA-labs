from functools import cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.sql import text

from app.config import settings


def _asyncpg_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


@cache
def get_engine() -> AsyncEngine:
    return create_async_engine(_asyncpg_url(settings.DATABASE_URL))


async def check_dependencies() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))
