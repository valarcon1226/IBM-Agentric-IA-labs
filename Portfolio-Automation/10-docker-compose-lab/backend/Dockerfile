# =============================================================================
# Multi-stage Dockerfile for FastAPI Gateway
# Stage 1: Install dependencies
# Stage 2: Production image (minimal, non-root)
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Production ---
FROM python:3.12-slim AS production

LABEL maintainer="automation-portfolio"
LABEL description="FastAPI Gateway for the Automation Portfolio Stack"

# Install curl for Docker health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app
COPY src/ ./src/

# Switch to non-root user
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
