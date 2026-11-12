"""Main FastAPI application module."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.deps import get_async_session, verify_api_token
from app.api.routes import alerts, export, products
from app.db.session import AsyncSession, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # Attempt table creation on startup
    try:
        await init_db()
    except Exception:
        # If DB not ready yet, docker-compose healthcheck will wait for postgres
        pass
    yield


app = FastAPI(
    title="E-Commerce Price Monitor API",
    version="1.0.0",
    description="Polite e-commerce price monitoring with official APIs, structured data, and webhook alerts.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check(
    response: Response,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Unauthenticated healthcheck verifying database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "error": str(exc)}


# Mount API v1 routes with Bearer token authentication
app.include_router(
    products.router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_token)],
)
app.include_router(
    alerts.router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_token)],
)
app.include_router(
    export.router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_token)],
)
