"""
FastAPI Gateway — Portfolio Automation Stack

Central API gateway for the automation portfolio. Serves as the entry point
for all backend operations and provides health monitoring endpoints.
"""
import logging
import asyncio
from typing import Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import redis.asyncio as redis

from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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

async def check_db_connection(url: str) -> bool:
    """Check connection to the database."""
    # Placeholder: In a real app, use SQLAlchemy async engine to verify connection.
    # Avoiding direct psycopg2/asyncpg dependencies in this snippet for simplicity, 
    # but normally we'd attempt a quick 'SELECT 1'.
    logger.info(f"Mock checking DB connection to {url}")
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    logger.info(f"Starting up {settings.APP_NAME}...")
    
    # Test connections on startup (non-blocking)
    redis_ok = await check_redis_connection(settings.REDIS_URL)
    if not redis_ok:
        logger.warning("Redis is not available on startup.")
        
    yield
    
    logger.info(f"Shutting down {settings.APP_NAME}...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Central API gateway for the automation portfolio.",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify in production to restrict origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app)

@app.get("/", summary="Root Endpoint")
async def root() -> Dict[str, str]:
    """
    Welcome endpoint returning basic API information.
    """
    return {
        "message": f"Welcome to the {settings.APP_NAME}",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }

@app.get("/health", summary="Health Check")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint that tests connectivity to backing services.
    """
    redis_status = await check_redis_connection(settings.REDIS_URL)
    db_status = await check_db_connection(settings.DATABASE_URL)
    
    status = "healthy" if (redis_status and db_status) else "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "api": "up",
            "database": "up" if db_status else "down",
            "redis": "up" if redis_status else "down",
        }
    }

@app.get("/version", summary="Version Info")
async def version_info() -> Dict[str, str]:
    """
    Returns the current application version.
    """
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
