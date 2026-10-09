from fastapi.testclient import TestClient

from app import dev_chat, main


def test_dev_chat_registered_when_dev_mode_true():
    # 401 (not 404) proves the route exists and the bearer check runs.
    client = TestClient(main.app)
    response = client.post("/dev/chat", json={"wa_id": "573001234567", "text": "hola"})
    assert response.status_code == 401


def test_dev_chat_requires_bearer_token():
    client = TestClient(main.app)
    response = client.post("/dev/chat", json={"wa_id": "573001234567", "text": "hola"})
    assert response.status_code == 401


def test_dev_chat_rejects_wrong_token():
    client = TestClient(main.app)
    response = client.post(
        "/dev/chat",
        json={"wa_id": "573001234567", "text": "hola"},
        headers={"Authorization": "Bearer wrong_key"},
    )
    assert response.status_code == 401


def test_dev_chat_returns_replies(monkeypatch):
    async def fake_process(wa_id, message_id, message_type, text):
        assert message_id is None
        assert message_type == "text"
        return ["respuesta de prueba"]

    monkeypatch.setattr(dev_chat, "process_incoming_message", fake_process)
    client = TestClient(main.app)
    response = client.post(
        "/dev/chat",
        json={"wa_id": "573001234567", "text": "hola"},
        headers={"Authorization": "Bearer test_dev_api_key"},
    )
    assert response.status_code == 200
    assert response.json() == {"replies": ["respuesta de prueba"]}


def test_dev_chat_validates_body():
    client = TestClient(main.app)
    response = client.post(
        "/dev/chat",
        json={"wa_id": "", "text": "hola"},
        headers={"Authorization": "Bearer test_dev_api_key"},
    )
    assert response.status_code == 422


def test_dev_chat_absent_when_dev_mode_false():
    app_without_dev_mode = main.create_app(dev_mode=False)
    client = TestClient(app_without_dev_mode)
    response = client.post("/dev/chat", json={"wa_id": "573001234567", "text": "hola"})
    assert response.status_code == 404


def test_dev_chat_present_when_dev_mode_true():
    app_with_dev_mode = main.create_app(dev_mode=True)
    client = TestClient(app_with_dev_mode)
    response = client.post("/dev/chat", json={"wa_id": "573001234567", "text": "hola"})
    assert response.status_code == 401  # route exists, just unauthenticated
