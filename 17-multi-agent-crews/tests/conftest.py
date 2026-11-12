import os
import threading
from http.server import ThreadingHTTPServer

import pytest

from fake_llm.server import Handler

# The fake LLM listens on a free port (never 11434, where a real Ollama may be running).
_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=_server.serve_forever, daemon=True).start()
os.environ["LLM_BASE_URL"] = f"http://127.0.0.1:{_server.server_port}/v1"
os.environ["LLM_MODEL"] = "fake"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"


@pytest.fixture(autouse=True)
def tmp_database(tmp_path, monkeypatch):
    """Each test gets its own SQLite file."""
    from sqlalchemy import create_engine

    from app import main

    engine = create_engine(f"sqlite:///{tmp_path / 'reports.db'}")
    main.Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "engine", engine)
