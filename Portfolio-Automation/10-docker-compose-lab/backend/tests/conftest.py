import os

# Inert values so src.main can be imported; nothing here opens a connection.
TEST_ENV = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "JWT_SECRET": "test-secret",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
