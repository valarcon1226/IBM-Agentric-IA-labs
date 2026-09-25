import os

# Settings() validates required variables at import time; provide inert test values.
# Nothing here opens a connection: SQLAlchemy, Celery, Redis and MinIO clients connect lazily.
TEST_ENV = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "test",
    "MINIO_SECRET_KEY": "test",
    "MINIO_BUCKET": "test",
    "JWT_SECRET": "test",
    "API_KEY": "test",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
