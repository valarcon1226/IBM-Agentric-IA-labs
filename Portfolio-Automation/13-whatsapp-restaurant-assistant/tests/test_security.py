import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.security import mask_wa_id, verify_dev_api_key


def test_verify_dev_api_key_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        verify_dev_api_key(credentials=None)
    assert exc_info.value.status_code == 401


def test_verify_dev_api_key_wrong_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong_token")
    with pytest.raises(HTTPException) as exc_info:
        verify_dev_api_key(credentials=credentials)
    assert exc_info.value.status_code == 401


def test_verify_dev_api_key_right_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_dev_api_key")
    assert verify_dev_api_key(credentials=credentials) == "test_dev_api_key"


@pytest.mark.parametrize(
    ("wa_id", "expected"),
    [
        ("573001234567", "57300***4567"),
        ("12345", "*****"),
        ("123456789", "*********"),
        ("1234567890", "12345***7890"),
    ],
)
def test_mask_wa_id(wa_id, expected):
    assert mask_wa_id(wa_id) == expected
