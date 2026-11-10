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


def test_app_starts_without_widget_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("WIDGET_DIR", str(tmp_path / "missing"))
    client = TestClient(main.create_app(dev_mode=False))
    assert client.get("/widget/").status_code == 404
    assert client.get("/health").status_code in (200, 503)


def test_widget_served_when_folder_exists(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<h1>widget</h1>")
    monkeypatch.setenv("WIDGET_DIR", str(tmp_path))
    client = TestClient(main.create_app(dev_mode=False))
    response = client.get("/widget/")
    assert response.status_code == 200
    assert "widget" in response.text


def test_session_id_length_limit(monkeypatch):
    async def fake_process(wa_id, message_id, message_type, text):
        return ["ok"]

    monkeypatch.setattr(web_chat, "process_incoming_message", fake_process)
    client = TestClient(main.app)
    assert (
        client.post("/web/chat", json={"session_id": "a" * 17, "text": "hola"}).status_code == 422
    )
    assert (
        client.post("/web/chat", json={"session_id": "a" * 16, "text": "hola"}).status_code == 200
    )
