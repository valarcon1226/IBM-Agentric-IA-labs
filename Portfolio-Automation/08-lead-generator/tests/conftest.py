import os

TEST_ENV = {
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/test",
    "API_KEY": "test_api_key",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
