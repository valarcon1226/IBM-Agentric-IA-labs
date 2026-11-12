import os

from dotenv import load_dotenv

load_dotenv()

# Any OpenAI-compatible endpoint: Ollama by default, the fake LLM in tests and docker compose.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/reports.db")
