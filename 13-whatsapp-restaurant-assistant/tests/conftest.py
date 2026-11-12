import os

TEST_ENV = {
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/test",
    "LLM_BASE_URL": "http://localhost:9000/v1",
    "LLM_API_KEY": "test_llm_api_key",
    "LLM_MODEL": "test-model",
    "LLM_FAKE": "false",
    "WHATSAPP_ENABLED": "false",
    "DEV_MODE": "true",
    "DEV_API_KEY": "test_dev_api_key",
    "GRAPH_API_VERSION": "v23.0",
    "GRAPH_API_BASE": "http://localhost:9000",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
