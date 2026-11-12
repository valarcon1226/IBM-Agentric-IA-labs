from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.models.database import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize tables on startup if database is accessible
    try:
        init_db()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Task Scheduler Engine",
    version="1.0.0",
    description="Dynamic DB-backed scheduled tasks with Celery Beat and FastAPI",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    # Check DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unreachable: {exc}") from exc

    # Check Redis
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=3.0)
        r.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unreachable: {exc}") from exc

    return {"status": "healthy"}
