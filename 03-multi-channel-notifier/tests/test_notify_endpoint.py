"""Endpoint tests for `/api/v1/notify|notifications|templates` (DECISIONES-03 N8/N9).

The DB layer (`app.notifications`) and the Celery `.apply_async` calls are mocked throughout —
these are unit tests of the FastAPI wiring, not integration tests against a real Postgres/Redis
(those are covered by the Docker smoke test in the batch report).
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app import main

AUTH = {"Authorization": "Bearer test_api_key"}


@pytest.fixture
def client():
    return TestClient(main.app)


def test_notify_requires_auth(client):
    response = client.post("/api/v1/notify", json={"template_name": "welcome_email"})
    assert response.status_code == 401


def test_notify_rejects_wrong_token(client):
    response = client.post(
        "/api/v1/notify",
        json={"template_name": "welcome_email", "channels": ["slack"]},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_notify_unknown_channel_returns_422(client):
    response = client.post(
        "/api/v1/notify",
        json={"template_name": "welcome_email", "channels": ["fax"]},
        headers=AUTH,
    )
    assert response.status_code == 422


def test_notify_unknown_template_returns_422(client, monkeypatch):
    response = client.post(
        "/api/v1/notify",
        json={
            "template_name": "does_not_exist",
            "channels": ["slack"],
            "recipients": {"slack": ["#alerts"]},
        },
        headers=AUTH,
    )
    assert response.status_code == 422
    assert "does_not_exist" in response.json()["detail"] or "Unknown template" in str(
        response.json()["detail"]
    )


def test_notify_missing_template_variable_returns_422(client):
    response = client.post(
        "/api/v1/notify",
        json={
            "template_name": "slack_alert",
            "channels": ["slack"],
            "recipients": {"slack": ["#alerts"]},
            "payload": {"severity": "critical"},  # missing "message" and "system"
        },
        headers=AUTH,
    )
    assert response.status_code == 422


def test_notify_success_queues_one_task_per_channel(client, monkeypatch):
    insert_mock = AsyncMock(
        return_value={"id": "11111111-1111-1111-1111-111111111111", "status": "queued"}
    )
    monkeypatch.setattr(main, "insert_notification", insert_mock)

    email_apply = MagicMock()
    slack_apply = MagicMock()
    monkeypatch.setattr(main.send_email_task, "apply_async", email_apply)
    monkeypatch.setattr(main.send_slack_task, "apply_async", slack_apply)

    response = client.post(
        "/api/v1/notify",
        json={
            "template_name": "welcome_email",
            "channels": ["email", "slack"],
            "priority": "high",
            "recipients": {
                "email": ["alice@example.com"],
                "slack": ["#alerts"],
            },
            "payload": {"user_name": "Alice", "system": "Data Intake Pipeline"},
        },
        headers=AUTH,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["notification_id"] == "11111111-1111-1111-1111-111111111111"
    assert body["status"] == "queued"

    insert_mock.assert_awaited_once()
    email_apply.assert_called_once()
    slack_apply.assert_called_once()
    assert email_apply.call_args.kwargs["priority"] == 0  # high -> 0
    assert slack_apply.call_args.kwargs["priority"] == 0


def test_get_notification_requires_auth(client):
    response = client.get("/api/v1/notifications/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 401


def test_get_notification_malformed_id_returns_404(client):
    response = client.get("/api/v1/notifications/not-a-uuid", headers=AUTH)
    assert response.status_code == 404


def test_get_notification_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(main, "get_notification", AsyncMock(return_value=None))
    response = client.get(
        "/api/v1/notifications/11111111-1111-1111-1111-111111111111", headers=AUTH
    )
    assert response.status_code == 404


def test_get_notification_found_returns_detail(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "get_notification",
        AsyncMock(
            return_value={
                "id": "11111111-1111-1111-1111-111111111111",
                "template_name": "welcome_email",
                "status": "completed",
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "delivery_logs": [
                    {
                        "channel": "email",
                        "status": "delivered",
                        "processed_at": datetime(2024, 1, 1, 12, 0, 5),
                    }
                ],
            }
        ),
    )
    response = client.get(
        "/api/v1/notifications/11111111-1111-1111-1111-111111111111", headers=AUTH
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["delivery_logs"][0]["channel"] == "email"


def test_list_notifications_requires_auth(client):
    response = client.get("/api/v1/notifications")
    assert response.status_code == 401


def test_list_notifications_limit_over_200_rejected(client):
    response = client.get("/api/v1/notifications?limit=201", headers=AUTH)
    assert response.status_code == 422


def test_list_notifications_filters_passed_through(client, monkeypatch):
    list_mock = AsyncMock(
        return_value=(
            [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "template_name": "welcome_email",
                    "status": "failed",
                    "created_at": datetime(2024, 1, 2, 15, 30, 0),
                }
            ],
            1,
        )
    )
    monkeypatch.setattr(main, "list_notifications", list_mock)

    response = client.get(
        "/api/v1/notifications?status=failed&since=2024-01-01&limit=10", headers=AUTH
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["status"] == "failed"
    list_mock.assert_awaited_once_with("failed", datetime(2024, 1, 1), 10)


def test_list_notifications_invalid_since_returns_422(client):
    response = client.get("/api/v1/notifications?since=not-a-date", headers=AUTH)
    assert response.status_code == 422


def test_templates_requires_auth(client):
    response = client.get("/api/v1/templates")
    assert response.status_code == 401


def test_templates_lists_available(client):
    response = client.get("/api/v1/templates", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"templates": ["daily_report", "slack_alert", "welcome_email"]}
