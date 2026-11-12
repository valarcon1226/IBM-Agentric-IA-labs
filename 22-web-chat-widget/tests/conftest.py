import pytest
import os
import threading
import uvicorn
import time
from playwright.sync_api import Page, expect

@pytest.fixture(scope="session", autouse=True)
def start_server():
    os.environ["LLM_FAKE"] = "true"
    os.environ["DEV_MODE"] = "true"
    os.environ["DEV_API_KEY"] = "test_dev_api_key"
    os.environ["ADMIN_API_KEY"] = "test_dev_api_key"
    os.environ["DATABASE_URL"] = "postgresql://postgres:test@localhost:5432/test"
    os.environ["LLM_BASE_URL"] = "http://localhost:9000/v1"
    os.environ["LLM_API_KEY"] = "test_llm_api_key"
    os.environ["LLM_MODEL"] = "test-model"
    
    import sys
    from pathlib import Path
    p13_dir = Path(__file__).parent.parent.parent / "13-whatsapp-restaurant-assistant"
    sys.path.insert(0, str(p13_dir))
    
    from tests.test_tools import FakeDB, FakeResult
    
    global_fake_db = FakeDB()
    original_execute = global_fake_db.execute
    def new_execute(self, sql, params):
        if "FROM messages" in sql or "FROM handovers" in sql or "FROM customers" in sql:
            return FakeResult(rows=[])
        return original_execute(sql, params)
    
    import types
    global_fake_db.execute = types.MethodType(new_execute, global_fake_db)
    
    pytest.fake_db = global_fake_db
    
    from app import database, tools, conversation, admin, agent
    
    database.get_engine = lambda: global_fake_db
    tools.get_engine = lambda: global_fake_db
    if hasattr(conversation, "get_engine"):
        conversation.get_engine = lambda: global_fake_db
    if hasattr(agent, "get_engine"):
        agent.get_engine = lambda: global_fake_db
    
    async def fake_check_deps():
        pass
    database.check_dependencies = fake_check_deps

    async def fake_record_message(*args, **kwargs):
        pass
    conversation.record_message = fake_record_message
    
    async def fake_check_rate(*args, **kwargs):
        return True, False
    conversation.check_rate_limit = fake_check_rate
    
    async def fake_mark(*args, **kwargs):
        pass
    conversation.mark_processed = fake_mark
    
    from app.main import app
    
    config = uvicorn.Config(app, host="127.0.0.1", port=8004, log_level="info")
    server = uvicorn.Server(config)
    
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)
    
    yield
