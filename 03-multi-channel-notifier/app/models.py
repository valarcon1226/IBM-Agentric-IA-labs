import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings

VALID_CHANNELS = frozenset({"email", "slack", "telegram", "discord"})
MAX_RECIPIENTS = 50
MAX_PAYLOAD_BYTES = 10_240  # ~10 KB (README §10 / DECISIONES-03 N6)

_TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_TELEGRAM_CHAT_ID_RE = re.compile(r"^-?\d+$")
# Simple, dependency-free email check (good enough for request validation; no deliverability claim).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NotifyRequest(BaseModel):
    template_name: str
    channels: list[str]
    priority: Literal["low", "medium", "high"] = "medium"
    recipients: dict[str, list[str]] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None

    @field_validator("template_name")
    @classmethod
    def validate_template_name(cls, value: str) -> str:
        if not _TEMPLATE_NAME_RE.match(value):
            raise ValueError("template_name must match ^[a-z0-9_]+$")
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one channel is required")
        if len(value) != len(set(value)):
            raise ValueError("Duplicate channels are not allowed")
        unknown = sorted(set(value) - VALID_CHANNELS)
        if unknown:
            raise ValueError(f"Unsupported channel(s): {', '.join(unknown)}")
        return value

    @model_validator(mode="after")
    def validate_configured_channels(self) -> "NotifyRequest":
        unconfigured = sorted(c for c in self.channels if c not in settings.configured_channels)
        if unconfigured:
            raise ValueError(f"Channel(s) not configured: {', '.join(unconfigured)}")
        return self

    @model_validator(mode="after")
    def validate_recipients(self) -> "NotifyRequest":
        if "email" in self.channels:
            emails = self.recipients.get("email") or []
            if not emails:
                raise ValueError("recipients.email is required for the email channel")
            if len(emails) > MAX_RECIPIENTS:
                raise ValueError(f"recipients.email exceeds the maximum of {MAX_RECIPIENTS}")
            invalid = [e for e in emails if not _EMAIL_RE.match(e)]
            if invalid:
                raise ValueError(f"Invalid email address(es): {', '.join(invalid)}")

        if "telegram" in self.channels:
            chat_ids = self.recipients.get("telegram") or []
            if not chat_ids:
                raise ValueError("recipients.telegram is required for the telegram channel")
            if len(chat_ids) > MAX_RECIPIENTS:
                raise ValueError(f"recipients.telegram exceeds the maximum of {MAX_RECIPIENTS}")
            invalid = [c for c in chat_ids if not _TELEGRAM_CHAT_ID_RE.match(c)]
            if invalid:
                raise ValueError(f"Invalid telegram chat id(s): {', '.join(invalid)}")

        for channel in ("slack", "discord"):
            recipients = self.recipients.get(channel)
            if recipients and len(recipients) > MAX_RECIPIENTS:
                raise ValueError(f"recipients.{channel} exceeds the maximum of {MAX_RECIPIENTS}")

        return self

    @model_validator(mode="after")
    def validate_payload_size(self) -> "NotifyRequest":
        if len(self.model_dump_json().encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Request payload exceeds {MAX_PAYLOAD_BYTES} bytes")
        return self

    @model_validator(mode="after")
    def validate_subject_no_header_injection(self) -> "NotifyRequest":
        # payload["subject"] ends up in the email "Subject" header (app.templating.email_subject).
        # A CR or LF there would let a caller inject extra headers/body into the outgoing email
        # (classic SMTP header injection) — reject instead of silently sanitizing.
        if self.payload is not None:
            subject = self.payload.get("subject")
            if isinstance(subject, str) and ("\r" in subject or "\n" in subject):
                raise ValueError("payload.subject must not contain CR or LF characters")
        return self


class NotifyResponse(BaseModel):
    notification_id: str
    status: str
    message: str


class DeliveryLogEntry(BaseModel):
    channel: str
    status: str
    processed_at: datetime


class NotificationDetail(BaseModel):
    id: str
    template_name: str
    status: str
    created_at: datetime
    delivery_logs: list[DeliveryLogEntry]


class NotificationListItem(BaseModel):
    id: str
    template_name: str
    status: str
    created_at: datetime


class NotificationListResponse(BaseModel):
    results: list[NotificationListItem]
    total: int


class TemplatesResponse(BaseModel):
    templates: list[str]
