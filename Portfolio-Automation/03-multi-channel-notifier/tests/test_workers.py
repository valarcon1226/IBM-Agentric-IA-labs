"""Unit tests for the per-channel Celery tasks (DECISIONES-03 N7/N9): success calls the mocked
client exactly once, a transient error retries, and a permanent (4xx) error fails without a
retry. All clients are mocked — no real SMTP/HTTP/DB.
"""

from unittest.mock import MagicMock

import pytest

from app.workers import discord_task, email_task, slack_task, telegram_task
from app.workers.common import PermanentDeliveryError, TransientDeliveryError


class _RetryCalled(Exception):
    """Sentinel raised by the mocked `self.retry` so tests can assert it was invoked."""


def _with_request(task, retries):
    task.push_request(retries=retries)
    return task


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


class _FakeSMTP:
    def __init__(self, send_message=None, has_extn=False):
        self._send_message = send_message or MagicMock()
        self._has_extn = has_extn

    def __call__(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def has_extn(self, name):
        return self._has_extn

    def login(self, user, password):
        pass

    def send_message(self, message):
        self._send_message(message)


def test_email_success_calls_smtp_once(monkeypatch):
    send_message = MagicMock()
    monkeypatch.setattr(email_task.smtplib, "SMTP", _FakeSMTP(send_message=send_message))
    log_calls = []
    monkeypatch.setattr(
        email_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )

    _with_request(email_task.send_email_task, retries=0)
    try:
        email_task.send_email_task.run("nid-1", ["alice@example.com"], "Subject", "Body text", None)
    finally:
        email_task.send_email_task.pop_request()

    assert send_message.call_count == 1
    assert log_calls[-1][0][2] == "delivered"


def test_email_timeout_retries(monkeypatch):
    def raise_timeout(*a, **k):
        raise TimeoutError("smtp timed out")

    monkeypatch.setattr(
        email_task.smtplib, "SMTP", _FakeSMTP(send_message=MagicMock(side_effect=raise_timeout))
    )
    log_calls = []
    monkeypatch.setattr(
        email_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )
    monkeypatch.setattr(
        email_task.send_email_task,
        "retry",
        MagicMock(side_effect=_RetryCalled()),
    )

    _with_request(email_task.send_email_task, retries=0)
    try:
        with pytest.raises(_RetryCalled):
            email_task.send_email_task.run("nid-2", ["a@example.com"], "S", "Body", None)
    finally:
        email_task.send_email_task.pop_request()

    assert log_calls[-1][0][2] == "retrying"
    email_task.send_email_task.retry.assert_called_once()


def test_email_permanent_failure_no_retry(monkeypatch):
    import smtplib

    def raise_rejected(*a, **k):
        raise smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"rejected")})

    monkeypatch.setattr(
        email_task.smtplib, "SMTP", _FakeSMTP(send_message=MagicMock(side_effect=raise_rejected))
    )
    log_calls = []
    monkeypatch.setattr(
        email_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )
    retry_mock = MagicMock(side_effect=_RetryCalled())
    monkeypatch.setattr(email_task.send_email_task, "retry", retry_mock)

    _with_request(email_task.send_email_task, retries=0)
    try:
        email_task.send_email_task.run("nid-3", ["a@example.com"], "S", "Body", None)
    finally:
        email_task.send_email_task.pop_request()

    assert log_calls[-1][0][2] == "failed"
    retry_mock.assert_not_called()


def test_email_retries_exhausted_marks_failed(monkeypatch):
    def raise_timeout(*a, **k):
        raise TimeoutError("smtp timed out")

    monkeypatch.setattr(
        email_task.smtplib, "SMTP", _FakeSMTP(send_message=MagicMock(side_effect=raise_timeout))
    )
    log_calls = []
    monkeypatch.setattr(
        email_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )
    retry_mock = MagicMock(side_effect=_RetryCalled())
    monkeypatch.setattr(email_task.send_email_task, "retry", retry_mock)

    _with_request(email_task.send_email_task, retries=5)  # == max_retries
    try:
        email_task.send_email_task.run("nid-4", ["a@example.com"], "S", "Body", None)
    finally:
        email_task.send_email_task.pop_request()

    assert log_calls[-1][0][2] == "failed"
    retry_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Slack / Discord (same shape, parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", [slack_task, discord_task])
def test_webhook_success_calls_client_once(monkeypatch, module):
    post = MagicMock()
    monkeypatch.setattr(module, "post_webhook_json", post)
    log_calls = []
    monkeypatch.setattr(module, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k)))

    task = module.send_slack_task if module is slack_task else module.send_discord_task
    _with_request(task, retries=0)
    try:
        task.run("nid-5", "hello world")
    finally:
        task.pop_request()

    assert post.call_count == 1
    assert log_calls[-1][0][2] == "delivered"


@pytest.mark.parametrize("module", [slack_task, discord_task])
def test_webhook_transient_error_retries(monkeypatch, module):
    monkeypatch.setattr(
        module, "post_webhook_json", MagicMock(side_effect=TransientDeliveryError("HTTP 503"))
    )
    log_calls = []
    monkeypatch.setattr(module, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k)))

    task = module.send_slack_task if module is slack_task else module.send_discord_task
    retry_mock = MagicMock(side_effect=_RetryCalled())
    monkeypatch.setattr(task, "retry", retry_mock)

    _with_request(task, retries=0)
    try:
        with pytest.raises(_RetryCalled):
            task.run("nid-6", "hello world")
    finally:
        task.pop_request()

    assert log_calls[-1][0][2] == "retrying"
    retry_mock.assert_called_once()


@pytest.mark.parametrize("module", [slack_task, discord_task])
def test_webhook_permanent_error_no_retry(monkeypatch, module):
    monkeypatch.setattr(
        module, "post_webhook_json", MagicMock(side_effect=PermanentDeliveryError("HTTP 400"))
    )
    log_calls = []
    monkeypatch.setattr(module, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k)))

    task = module.send_slack_task if module is slack_task else module.send_discord_task
    retry_mock = MagicMock(side_effect=_RetryCalled())
    monkeypatch.setattr(task, "retry", retry_mock)

    _with_request(task, retries=0)
    try:
        task.run("nid-7", "hello world")
    finally:
        task.pop_request()

    assert log_calls[-1][0][2] == "failed"
    retry_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Telegram (one sendMessage per chat id, inside a single task)
# ---------------------------------------------------------------------------


def test_telegram_success_calls_client_once_per_chat_id(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr(telegram_task, "post_webhook_json", post)
    log_calls = []
    monkeypatch.setattr(
        telegram_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )

    _with_request(telegram_task.send_telegram_task, retries=0)
    try:
        telegram_task.send_telegram_task.run("nid-8", ["111", "222", "333"], "hello")
    finally:
        telegram_task.send_telegram_task.pop_request()

    assert post.call_count == 3
    assert log_calls[-1][0][2] == "delivered"


def test_telegram_transient_error_retries(monkeypatch):
    monkeypatch.setattr(
        telegram_task,
        "post_webhook_json",
        MagicMock(side_effect=TransientDeliveryError("HTTP 429")),
    )
    log_calls = []
    monkeypatch.setattr(
        telegram_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )
    retry_mock = MagicMock(side_effect=_RetryCalled())
    monkeypatch.setattr(telegram_task.send_telegram_task, "retry", retry_mock)

    _with_request(telegram_task.send_telegram_task, retries=0)
    try:
        with pytest.raises(_RetryCalled):
            telegram_task.send_telegram_task.run("nid-9", ["111"], "hello")
    finally:
        telegram_task.send_telegram_task.pop_request()

    assert log_calls[-1][0][2] == "retrying"
    retry_mock.assert_called_once()


def test_telegram_permanent_error_no_retry(monkeypatch):
    monkeypatch.setattr(
        telegram_task,
        "post_webhook_json",
        MagicMock(side_effect=PermanentDeliveryError("HTTP 400")),
    )
    log_calls = []
    monkeypatch.setattr(
        telegram_task, "log_delivery_attempt", lambda *a, **k: log_calls.append((a, k))
    )
    retry_mock = MagicMock(side_effect=_RetryCalled())
    monkeypatch.setattr(telegram_task.send_telegram_task, "retry", retry_mock)

    _with_request(telegram_task.send_telegram_task, retries=0)
    try:
        telegram_task.send_telegram_task.run("nid-10", ["111"], "hello")
    finally:
        telegram_task.send_telegram_task.pop_request()

    assert log_calls[-1][0][2] == "failed"
    retry_mock.assert_not_called()
