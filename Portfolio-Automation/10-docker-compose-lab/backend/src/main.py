"""
FastAPI Gateway — Portfolio Automation Stack

Central API gateway for the automation portfolio. Serves as the entry point
for all backend operations and provides health monitoring endpoints.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import create_engine, text

from .config import require_api_settings, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

require_api_settings(settings)
assert settings.DATABASE_URL is not None  # guaranteed by require_api_settings
_db_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


async def check_redis_connection(url: str) -> bool:
    """Check connection to Redis."""
    try:
        client = redis.from_url(url, socket_timeout=2.0)
        await client.ping()
        await client.close()
        return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return False


async def check_db_connection() -> bool:
    """Run SELECT 1 against the database without blocking the event loop."""

    def _ping() -> None:
        with _db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    try:
        await asyncio.to_thread(_ping)
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info(f"Starting up {settings.APP_NAME}...")
    if not await check_redis_connection(settings.REDIS_URL):
        logger.warning("Redis is not available on startup.")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Central API gateway for the automation portfolio.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify in production to restrict origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)


@app.get("/", summary="Root Endpoint")
async def root() -> dict[str, str]:
    """Welcome endpoint returning basic API information."""
    return {
        "message": f"Welcome to the {settings.APP_NAME}",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


@app.get("/health", summary="Health Check")
async def health_check() -> JSONResponse:
    """Real dependency check. Returns 503 when a dependency is down so that the
    Docker healthcheck (curl -f /health) marks the container unhealthy."""
    redis_ok = await check_redis_connection(settings.REDIS_URL)
    db_ok = await check_db_connection()
    healthy = redis_ok and db_ok
    body: dict[str, Any] = {
        "status": "healthy" if healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "api": "up",
            "database": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
    }
    return JSONResponse(status_code=200 if healthy else 503, content=body)


@app.get("/version", summary="Version Info")
async def version_info() -> dict[str, str]:
    """Returns the current application version."""
    return {"app_name": settings.APP_NAME, "version": settings.APP_VERSION}
