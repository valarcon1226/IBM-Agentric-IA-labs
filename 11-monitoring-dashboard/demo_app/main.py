import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

from demo_app.config import settings

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------
logger = logging.getLogger("demo_app")
logger.setLevel(logging.INFO)

log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] [app=demo-app] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

# Stream handler for stdout/stderr
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File handler for Loki/Promtail (fallback safely if directory is not writable)
log_file = settings.log_file_path
try:
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
except Exception as e:
    logger.warning("Could not open log file %s: %s. Using stdout only.", log_file, e)

# ---------------------------------------------------------
# Prometheus Metrics Definitions
# ---------------------------------------------------------
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

BUSINESS_PROCESSED_ROWS_TOTAL = Counter(
    "business_processed_rows_total",
    "Total data rows processed across business automation pipelines",
    ["pipeline", "status"],
)

BUSINESS_ACTIVE_USERS = Gauge(
    "business_active_users",
    "Current active business users in the platform",
)

BUSINESS_OPERATIONS_TOTAL = Counter(
    "business_operations_total",
    "Total business operations triggered",
    ["operation_type"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initial state for gauge
    BUSINESS_ACTIVE_USERS.set(42)
    logger.info("Demo app started successfully. Active users gauge initialized to 42.")
    yield
    logger.info("Demo app shutting down.")


app = FastAPI(
    title="Portfolio Monitoring Demo App",
    description="FastAPI service instrumented with Prometheus metrics and structured logs",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Metrics & Request Tracking Middleware
# ---------------------------------------------------------
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    method = request.method
    path = request.url.path

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        logger.error(
            "Unhandled exception during request method=%s path=%s error=%s",
            method,
            path,
            str(exc),
        )
        raise exc
    finally:
        duration = time.perf_counter() - start_time
        # Record metrics
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=path, status=str(status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=path).observe(duration)
        logger.info(
            "Request finished method=%s path=%s status=%s duration=%.4fs",
            method,
            path,
            status_code,
            duration,
        )


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class ProcessRequest(BaseModel):
    rows: int = Field(default=100, ge=1, le=100000, description="Number of rows to process")
    pipeline: str = Field(default="data_cleaning", description="Pipeline identifier")


class Item(BaseModel):
    id: int
    name: str
    status: str


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "demo-app", "version": "1.0.0"}


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics in text format."""
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/api/items")
async def get_items() -> dict[str, Any]:
    """Sample business endpoint returning items."""
    BUSINESS_OPERATIONS_TOTAL.labels(operation_type="query_items").inc()
    items = [
        {"id": 1, "name": "Report Alpha", "status": "active"},
        {"id": 2, "name": "Dataset Beta", "status": "processed"},
        {"id": 3, "name": "Invoice Gamma", "status": "pending"},
    ]
    logger.info("Retrieved %d sample items", len(items))
    return {"items": items, "count": len(items)}


@app.post("/api/process")
async def process_rows(payload: ProcessRequest) -> dict[str, Any]:
    """Sample business endpoint simulating batch row processing."""
    BUSINESS_PROCESSED_ROWS_TOTAL.labels(pipeline=payload.pipeline, status="success").inc(
        payload.rows
    )
    BUSINESS_OPERATIONS_TOTAL.labels(operation_type="batch_processing").inc()
    logger.info(
        "Successfully processed %d rows in pipeline=%s",
        payload.rows,
        payload.pipeline,
    )
    return {
        "pipeline": payload.pipeline,
        "processed_rows": payload.rows,
        "status": "completed",
    }


@app.get("/api/error")
async def trigger_error() -> JSONResponse:
    """Endpoint simulating an internal server error (500) to verify error-rate alerting."""
    logger.error("Synthetic 500 error triggered for alert verification on endpoint /api/error")
    raise HTTPException(
        status_code=500,
        detail="Synthetic internal server error triggered for monitoring verification",
    )


@app.get("/api/slow")
async def trigger_slow(delay: float = 0.6) -> dict[str, Any]:
    """Endpoint simulating high latency to verify latency alerting."""
    logger.warning("Simulated slow request started with delay=%.2fs", delay)
    await asyncio.sleep(delay)
    BUSINESS_OPERATIONS_TOTAL.labels(operation_type="slow_simulation").inc()
    logger.info("Simulated slow request finished after %.2fs", delay)
    return {"delay_seconds": delay, "message": "Slow request finished"}
