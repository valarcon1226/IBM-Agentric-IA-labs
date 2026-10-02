import os

TEST_ENV = {
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/test",
    "API_KEY": "test_api_key",
    "CH_API_KEY": "test_ch_api_key",
    "INSEE_API_KEY": "test_insee_api_key",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
