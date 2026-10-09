from fastapi.testclient import TestClient

from app import main, web_chat


def test_web_chat_endpoint(monkeypatch):
    async def fake_process(wa_id, message_id, message_type, text):
        return ["respuesta de prueba"]

    monkeypatch.setattr(web_chat, "process_incoming_message", fake_process)
    client = TestClient(main.app)
    response = client.post("/web/chat", json={"session_id": "test1", "text": "hola"})
    assert response.status_code == 200
    assert response.json() == {"replies": ["respuesta de prueba"]}


def test_admin_upload_rejects_without_auth(monkeypatch):
    import app.config

    monkeypatch.setattr(app.config.settings, "ADMIN_API_KEY", "test_key")
    client = TestClient(main.app)
    response = client.post("/admin/upload", files={"file": ("test.md", b"foo")})
    assert response.status_code == 401


def test_admin_upload_accepts_md(monkeypatch, tmp_path):
    import app.config

    monkeypatch.setattr(app.config.settings, "ADMIN_API_KEY", "test_key")

    import app.admin

    monkeypatch.setattr(app.admin, "KNOWLEDGE_DIR", tmp_path)

    app_for_test = main.create_app(dev_mode=True)
    client = TestClient(app_for_test)

    response = client.post(
        "/admin/upload",
        files={"file": ("test.md", b"foo")},
        headers={"Authorization": "Bearer test_key"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Archivo subido y base de conocimiento reindexada.",
    }
