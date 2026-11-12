import json
from uuid import uuid4

import httpx
import pytest
from frontend.app import get_pending_reviews, submit_review

API_URL = "http://api.example.test"
API_KEY = "test-api-key"
UPLOAD_ID = str(uuid4())
RECORD_ID = str(uuid4())


def test_get_pending_reviews_sends_bearer_and_returns_data():
    item = {
        "record_id": RECORD_ID,
        "upload_id": UPLOAD_ID,
        "line_number": 3,
        "data": {"first_name": "Jane", "company": ""},
        "reasons": ["Missing company"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == f"{API_URL}/api/v1/intake/{UPLOAD_ID}/review"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        return httpx.Response(200, json={"upload_id": UPLOAD_ID, "pending_reviews": [item]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = get_pending_reviews(client, API_URL, API_KEY, UPLOAD_ID)

    assert result == [item]


def test_submit_approve_sends_corrected_data():
    corrected_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@smith.com",
        "phone": "555-0199",
        "company": "Smith LLC",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{API_URL}/api/v1/intake/{UPLOAD_ID}/review"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        assert json.loads(request.content) == {
            "record_id": RECORD_ID,
            "action": "approve",
            "corrected_data": corrected_data,
        }
        return httpx.Response(200, json={"status": "success", "message": "approved"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submit_review(client, API_URL, API_KEY, UPLOAD_ID, RECORD_ID, "approve", corrected_data)


def test_submit_reject_omits_corrected_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"record_id": RECORD_ID, "action": "reject"}
        return httpx.Response(200, json={"status": "success", "message": "rejected"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submit_review(client, API_URL, API_KEY, UPLOAD_ID, RECORD_ID, "reject")


def test_api_status_errors_are_not_suppressed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Upload not found"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError) as error:
            get_pending_reviews(client, API_URL, API_KEY, UPLOAD_ID)

    assert error.value.response.status_code == 404
