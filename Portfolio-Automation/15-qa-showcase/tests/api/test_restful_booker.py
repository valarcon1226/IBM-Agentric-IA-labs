import time

import httpx
import pytest

BASE_URL = "https://restful-booker.herokuapp.com"


@pytest.fixture(autouse=True)
def slow_down_tests():
    time.sleep(1)


@pytest.fixture(scope="module")
def auth_token():
    payload = {"username": "admin", "password": "password123"}
    response = httpx.post(f"{BASE_URL}/auth", json=payload)
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture
def create_booking():
    payload = {
        "firstname": "Jim",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {"checkin": "2024-01-01", "checkout": "2024-01-10"},
        "additionalneeds": "Breakfast",
    }
    response = httpx.post(f"{BASE_URL}/booking", json=payload)
    assert response.status_code == 200
    booking_id = response.json()["bookingid"]
    yield booking_id


def test_get_booking_ids():
    response = httpx.get(f"{BASE_URL}/booking")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "bookingid" in data[0]
        assert isinstance(data[0]["bookingid"], int)


def test_get_booking(create_booking):
    booking_id = create_booking
    response = httpx.get(f"{BASE_URL}/booking/{booking_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["firstname"] == "Jim"
    assert data["lastname"] == "Brown"
    assert isinstance(data["totalprice"], int)


def test_create_booking():
    payload = {
        "firstname": "Sally",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {"checkin": "2024-02-01", "checkout": "2024-02-10"},
        "additionalneeds": "Breakfast",
    }
    response = httpx.post(f"{BASE_URL}/booking", json=payload)
    assert response.status_code == 200
    assert "bookingid" in response.json()


def test_update_booking(auth_token, create_booking):
    booking_id = create_booking
    payload = {
        "firstname": "James",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {"checkin": "2024-01-01", "checkout": "2024-01-10"},
        "additionalneeds": "Breakfast",
    }
    headers = {"Cookie": f"token={auth_token}", "Accept": "application/json"}
    response = httpx.put(f"{BASE_URL}/booking/{booking_id}", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["firstname"] == "James"


def test_delete_booking(auth_token, create_booking):
    booking_id = create_booking
    headers = {"Cookie": f"token={auth_token}"}
    response = httpx.delete(f"{BASE_URL}/booking/{booking_id}", headers=headers)
    assert response.status_code == 201


def test_api_negative_invalid_token(create_booking):
    booking_id = create_booking
    payload = {
        "firstname": "James",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {"checkin": "2024-01-01", "checkout": "2024-01-10"},
    }
    headers = {"Cookie": "token=invalid_token", "Accept": "application/json"}

    response = httpx.put(f"{BASE_URL}/booking/{booking_id}", json=payload, headers=headers)
    assert response.status_code == 403

    response = httpx.delete(f"{BASE_URL}/booking/{booking_id}", headers=headers)
    assert response.status_code == 403


def test_api_negative_non_existent_id():
    response = httpx.get(f"{BASE_URL}/booking/999999999")
    assert response.status_code == 404


def test_api_negative_post_missing_data():
    payload = {
        "firstname": "Jim",
        # lastname is missing
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {"checkin": "2024-01-01", "checkout": "2024-01-10"},
    }
    response = httpx.post(f"{BASE_URL}/booking", json=payload)
    assert response.status_code == 500  # API returns 500 for missing data
