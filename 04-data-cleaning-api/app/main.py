from contextlib import asynccontextmanager

import redis
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import clean, enrich, jobs, schemas, transform, upload, validate
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: setup resources
    yield
    # Shutdown: cleanup resources
    pass


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

# /health, / and /metrics stay public; every /api/v1 route requires the API key.
for module in (clean, validate, transform, enrich, upload, jobs, schemas):
    app.include_router(module.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint checking DB and Redis."""
    health_status = {"status": "ok", "db": "ok", "redis": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["db"] = f"error: {str(e)}"
        health_status["status"] = "error"

    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "error"

    if health_status["status"] == "error":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_status)

    return health_status


@app.get("/", tags=["Info"])
def root_info():
    """Root endpoint with API info."""
    return {"app_name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}
