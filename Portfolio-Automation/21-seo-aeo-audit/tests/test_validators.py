"""Tests for URL and IP security validation."""

import pytest

from app.validators import is_local_hostname, is_private_or_loopback_ip, validate_url


def test_validate_url_valid_schemes():
    """Valid http and https URLs pass validation."""
    assert validate_url("https://ejemplo.com") == "https://ejemplo.com"
    assert validate_url("http://example.org/path?q=1") == "http://example.org/path?q=1"


def test_validate_url_rejects_empty():
    """Empty or None URL raises ValueError."""
    with pytest.raises(ValueError, match="no puede estar vacía"):
        validate_url("")


def test_validate_url_rejects_unsupported_schemes():
    """Schemes other than http/https raise ValueError."""
    with pytest.raises(ValueError, match="Esquema de URL no permitido"):
        validate_url("ftp://example.com/file.txt")

    with pytest.raises(ValueError, match="Esquema de URL no permitido"):
        validate_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="Esquema de URL no permitido"):
        validate_url("javascript:alert(1)")


def test_validate_url_rejects_private_ips_by_default():
    """Private and loopback IPs are blocked unless allow_local is True."""
    private_urls = [
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://10.0.0.1/admin",
        "http://192.168.1.100:8080",
        "http://172.16.0.5/",
    ]
    for url in private_urls:
        with pytest.raises(ValueError, match="local|privada"):
            validate_url(url, allow_local=False)


def test_validate_url_allows_local_when_flag_enabled():
    """Local addresses are accepted when allow_local is True."""
    assert validate_url("http://localhost:8016", allow_local=True) == "http://localhost:8016"
    assert validate_url("http://127.0.0.1:8899/test", allow_local=True) == "http://127.0.0.1:8899/test"


def test_ip_helpers():
    """Unit tests for IP helper predicates."""
    assert is_private_or_loopback_ip("127.0.0.1") is True
    assert is_private_or_loopback_ip("192.168.1.1") is True
    assert is_private_or_loopback_ip("8.8.8.8") is False
    assert is_private_or_loopback_ip("invalid_ip") is False

    assert is_local_hostname("localhost") is True
    assert is_local_hostname("my-service.local") is True
    assert is_local_hostname("google.com") is False
