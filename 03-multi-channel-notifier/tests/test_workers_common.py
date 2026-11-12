"""Unit tests for app.workers.common: HTTP-status classification and delivery logging/status
recompute SQL, both with mocked clients (no real network, no real Postgres).
"""

import urllib.error
from unittest.mock import MagicMock

import pytest

from app.workers import common
from app.workers.common import PermanentDeliveryError, TransientDeliveryError, post_webhook_json


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_post_webhook_json_success(monkeypatch):
    monkeypatch.setattr(common.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(200))
    post_webhook_json("http://example.invalid/hook", {"text": "hi"})  # no raise


def test_post_webhook_json_429_is_transient(monkeypatch):
    def raise_http_error(*a, **k):
        raise urllib.error.HTTPError("http://example.invalid", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", raise_http_error)
    with pytest.raises(TransientDeliveryError):
        post_webhook_json("http://example.invalid/hook", {})


def test_post_webhook_json_5xx_is_transient(monkeypatch):
    def raise_http_error(*a, **k):
        raise urllib.error.HTTPError("http://example.invalid", 503, "Unavailable", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", raise_http_error)
    with pytest.raises(TransientDeliveryError):
        post_webhook_json("http://example.invalid/hook", {})


def test_post_webhook_json_404_is_permanent(monkeypatch):
    def raise_http_error(*a, **k):
        raise urllib.error.HTTPError("http://example.invalid", 404, "Not Found", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", raise_http_error)
    with pytest.raises(PermanentDeliveryError):
        post_webhook_json("http://example.invalid/hook", {})


def test_post_webhook_json_network_error_is_transient(monkeypatch):
    def raise_url_error(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(common.urllib.request, "urlopen", raise_url_error)
    with pytest.raises(TransientDeliveryError):
        post_webhook_json("http://example.invalid/hook", {})


def test_post_webhook_json_never_includes_url_in_error(monkeypatch):
    def raise_http_error(*a, **k):
        raise urllib.error.HTTPError("http://example.invalid/hook?token=secret", 500, "x", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", raise_http_error)
    with pytest.raises(TransientDeliveryError) as exc_info:
        post_webhook_json("http://example.invalid/hook?token=secret", {})
    assert "example.invalid" not in str(exc_info.value)
    assert "token=secret" not in str(exc_info.value)


def test_retry_countdown_grows_with_retries_and_is_capped():
    # full_jitter=True means each call is random in [0, 2**retries), so compare the maximum
    # possible countdown at each retry count rather than exact values.
    max_at_0 = max(common.retry_countdown(0) for _ in range(50))
    max_at_3 = max(common.retry_countdown(3) for _ in range(50))
    max_at_20 = max(common.retry_countdown(20) for _ in range(50))

    assert 0 <= max_at_0 <= 1
    assert max_at_3 <= 8
    assert max_at_3 > max_at_0
    # Well past the cap, the interval collapses to [0, RETRY_BACKOFF_MAX_SECONDS].
    assert max_at_20 <= common.RETRY_BACKOFF_MAX_SECONDS
    assert max_at_20 > max_at_3


def test_log_delivery_attempt_inserts_then_recomputes_status(monkeypatch):
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    connection = MagicMock()
    connection.__enter__ = MagicMock(return_value=connection)
    connection.__exit__ = MagicMock(return_value=False)
    connection.cursor.return_value = cursor

    monkeypatch.setattr(common, "get_connection", lambda: connection)

    common.log_delivery_attempt("00000000-0000-0000-0000-000000000000", "email", "delivered", 1)

    assert cursor.execute.call_count == 2
    insert_sql = cursor.execute.call_args_list[0][0][0]
    update_sql = cursor.execute.call_args_list[1][0][0]
    assert "INSERT INTO delivery_logs" in insert_sql
    assert "UPDATE notifications" in update_sql
