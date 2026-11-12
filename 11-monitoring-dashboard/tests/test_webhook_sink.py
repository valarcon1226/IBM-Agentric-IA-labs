from fastapi.testclient import TestClient

from webhook_sink.sink import app

client = TestClient(app)


def test_webhook_sink_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_sink_receive_and_list_alert():
    # Clear first
    client.post("/alerts/clear")

    alert_payload = {
        "receiver": "webhook-sink",
        "status": "firing",
        "alerts": [
          {
            "status": "firing",
            "labels": {
              "alertname": "ServiceDown",
              "severity": "critical",
              "job": "demo-app",
            },
            "annotations": {
              "summary": "Demo App is down",
              "description": "demo-app target is down",
            },
            "startsAt": "2026-10-14T12:00:00Z",
          }
        ],
    }

    post_resp = client.post("/webhook", json=alert_payload)
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["status"] == "received"
    assert "ServiceDown" in post_data["latest_alerts"]

    list_resp = client.get("/alerts")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["count"] >= 1
    assert list_data["alerts"][0]["receiver"] == "webhook-sink"


def test_webhook_sink_clear():
    # Clear alerts
    response = client.post("/alerts/clear")
    assert response.status_code == 200
    assert response.json()["cleared"] is True

    # Confirm list is now empty
    list_resp = client.get("/alerts")
    assert list_resp.json()["count"] == 0
