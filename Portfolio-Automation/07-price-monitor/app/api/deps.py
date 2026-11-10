"""API dependencies."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_token
from app.db.session import get_async_session

__all__ = ["get_async_session", "verify_api_token", "AsyncSession", "Depends", "AsyncGenerator"]
