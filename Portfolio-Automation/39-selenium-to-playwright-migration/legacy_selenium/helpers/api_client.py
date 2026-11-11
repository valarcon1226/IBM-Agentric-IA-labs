"""API helper to provision isolated test data using only the standard library."""

from __future__ import annotations

import json
import time
import urllib.request
import uuid


def create_user(
    base_url: str = "http://127.0.0.1:3000",
    email: str | None = None,
    password: str = "TestUserPass123!",
    security_answer: str = "SeleniumSecurityAnswer",
) -> dict[str, str]:
    """Register a unique disposable user directly via the REST API."""
    if email is None:
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time() * 1000)
        email = f"user-{unique_id}-{timestamp}@juice-sh.op"

    payload = {
        "email": email,
        "password": password,
        "securityQuestion": {
            "id": 1,
            "question": "Your eldest siblings middle name?",
            "createdAt": "2026-01-01T00:00:00.000Z",
            "updatedAt": "2026-01-01T00:00:00.000Z",
        },
        "securityAnswer": security_answer,
    }

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/Users/",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 201:
            raise RuntimeError(f"User registration failed with status {resp.status}")

    return {
        "email": email,
        "password": password,
        "security_answer": security_answer,
    }
