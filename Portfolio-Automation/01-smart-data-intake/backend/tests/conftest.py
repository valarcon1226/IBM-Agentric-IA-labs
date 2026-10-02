import os

TEST_ENV = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "test",
    "MINIO_SECRET_KEY": "test",
    "API_KEY": "test",
    "N8N_RESUME_BASE_URL": "http://n8n:5678/webhook-waiting/",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
