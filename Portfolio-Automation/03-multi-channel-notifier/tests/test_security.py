import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.security import verify_api_key


def test_verify_api_key_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(credentials=None)
    assert exc_info.value.status_code == 401


def test_verify_api_key_wrong_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong_token")
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(credentials=credentials)
    assert exc_info.value.status_code == 401


def test_verify_api_key_right_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_api_key")
    assert verify_api_key(credentials=credentials) == "test_api_key"
