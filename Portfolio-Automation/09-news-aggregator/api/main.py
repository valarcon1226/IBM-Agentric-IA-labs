"""FastAPI application entry point for News Aggregator & Intelligence Reporter."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from api.database import PostgresDatabase, get_db
from api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("news_aggregator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema if running against PostgreSQL
    db = get_db()
    if isinstance(db, PostgresDatabase):
        try:
            db.init_schema()
        except Exception as exc:
            logger.warning(f"Could not initialize schema on startup (will retry on requests): {exc}")
    yield


app = FastAPI(
    title="News Aggregator & Intelligence Reporter API",
    version="1.0.0",
    description="Automated intelligence system that aggregates news, categorizes content, deduplicates via pgvector, and delivers HTML digests.",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    db = get_db()
    try:
        is_healthy = db.check_health()
        if not is_healthy:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unhealthy")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Database connection error: {exc}") from exc

    return {"status": "healthy", "service": "news-aggregator-api"}


app.include_router(router)
