import pytest
from pydantic import ValidationError

from app.models import NotifyRequest


def _base(**overrides):
    data = {
        "template_name": "welcome_email",
        "channels": ["email"],
        "recipients": {"email": ["alice@example.com"]},
        "payload": {"user_name": "Alice", "system": "Sys"},
    }
    data.update(overrides)
    return data


def test_valid_request_ok():
    request = NotifyRequest(**_base())
    assert request.priority == "medium"
    assert request.channels == ["email"]


def test_priority_values_accepted():
    for priority in ("low", "medium", "high"):
        assert NotifyRequest(**_base(priority=priority)).priority == priority


def test_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        NotifyRequest(**_base(priority="urgent"))


def test_template_name_invalid_characters_rejected():
    with pytest.raises(ValidationError):
        NotifyRequest(**_base(template_name="../etc/passwd"))


def test_template_name_uppercase_rejected():
    with pytest.raises(ValidationError):
        NotifyRequest(**_base(template_name="Welcome_Email"))


def test_empty_channels_rejected():
    with pytest.raises(ValidationError):
        NotifyRequest(**_base(channels=[]))


def test_duplicate_channels_rejected():
    with pytest.raises(ValidationError):
        NotifyRequest(**_base(channels=["email", "email"], recipients={"email": ["a@example.com"]}))


def test_unknown_channel_rejected():
    with pytest.raises(ValidationError):
        NotifyRequest(**_base(channels=["fax"]))


def test_unconfigured_channel_rejected(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(type(settings), "configured_channels", property(lambda self: set()))
    with pytest.raises(ValidationError, match="not configured"):
        NotifyRequest(**_base(channels=["email"]))


def test_email_requires_recipients():
    with pytest.raises(ValidationError, match="recipients.email is required"):
        NotifyRequest(**_base(recipients={}))


def test_email_recipients_over_limit_rejected():
    emails = [f"user{i}@example.com" for i in range(51)]
    with pytest.raises(ValidationError, match="exceeds the maximum"):
        NotifyRequest(**_base(recipients={"email": emails}))


def test_invalid_email_rejected():
    with pytest.raises(ValidationError, match="Invalid email"):
        NotifyRequest(**_base(recipients={"email": ["not-an-email"]}))


def test_telegram_requires_recipients():
    with pytest.raises(ValidationError, match="recipients.telegram is required"):
        NotifyRequest(**_base(channels=["telegram"], recipients={}))


def test_telegram_chat_id_valid():
    request = NotifyRequest(
        **_base(channels=["telegram"], recipients={"telegram": ["123456789", "-100200300"]})
    )
    assert request.recipients["telegram"] == ["123456789", "-100200300"]


def test_telegram_chat_id_invalid_rejected():
    with pytest.raises(ValidationError, match="Invalid telegram chat id"):
        NotifyRequest(**_base(channels=["telegram"], recipients={"telegram": ["not-a-chat-id"]}))


def test_telegram_recipients_over_limit_rejected():
    chat_ids = [str(i) for i in range(51)]
    with pytest.raises(ValidationError, match="exceeds the maximum"):
        NotifyRequest(**_base(channels=["telegram"], recipients={"telegram": chat_ids}))


def test_slack_recipients_optional():
    request = NotifyRequest(**_base(channels=["slack"], recipients={}))
    assert request.channels == ["slack"]


def test_slack_recipients_stored_if_present():
    request = NotifyRequest(**_base(channels=["slack"], recipients={"slack": ["#alerts"]}))
    assert request.recipients["slack"] == ["#alerts"]


def test_discord_recipients_optional():
    request = NotifyRequest(**_base(channels=["discord"], recipients={}))
    assert request.channels == ["discord"]


def test_slack_recipients_over_limit_rejected():
    recipients = [f"#chan{i}" for i in range(51)]
    with pytest.raises(ValidationError, match="exceeds the maximum"):
        NotifyRequest(**_base(channels=["slack"], recipients={"slack": recipients}))


def test_payload_too_large_rejected():
    with pytest.raises(ValidationError, match="exceeds"):
        NotifyRequest(**_base(payload={"blob": "x" * 20_000}))


def test_payload_subject_with_crlf_rejected():
    with pytest.raises(ValidationError, match="CR or LF"):
        NotifyRequest(**_base(payload={"subject": "Hi\r\nBcc: attacker@evil.com"}))


def test_payload_subject_with_lf_only_rejected():
    with pytest.raises(ValidationError, match="CR or LF"):
        NotifyRequest(**_base(payload={"subject": "Hi\nX-Injected: true"}))


def test_payload_subject_clean_accepted():
    request = NotifyRequest(**_base(payload={"subject": "Welcome aboard", "user_name": "Alice"}))
    assert request.payload is not None
    assert request.payload["subject"] == "Welcome aboard"
