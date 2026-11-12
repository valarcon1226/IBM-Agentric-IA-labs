"""Main FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.models.database import init_db
from app.services.storage import storage_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database tables and storage bucket."""
    logger.info("Initializing Invoice Processor microservice...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.warning("Could not automatically initialize DB on startup: %s", exc)

    try:
        storage_service.ensure_bucket()
        logger.info("MinIO storage verified.")
    except Exception as exc:
        logger.warning("Could not connect to MinIO on startup: %s", exc)

    yield

    logger.info("Shutting down Invoice Processor microservice.")


app = FastAPI(
    title="Invoice Processor & Validator API",
    description="Microservice for OCR-based invoice processing, rule validation, and export.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """Service health check endpoint."""
    return {"status": "ok", "service": "invoice-processor"}


app.include_router(api_router)
