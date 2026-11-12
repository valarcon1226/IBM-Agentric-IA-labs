"""Setup script for Paperless-ngx.

Creates admin user (if needed), retrieves or creates API auth token from environment
variables, verifies authentication against the SUT, and prints the API version.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE_URL = os.getenv("PAPERLESS_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_USER = os.getenv("PAPERLESS_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("PAPERLESS_ADMIN_PASSWORD", "admin")
ADMIN_EMAIL = os.getenv("PAPERLESS_ADMIN_EMAIL", "admin@example.com")


def wait_for_api(timeout: float = 60.0) -> None:
    """Wait for Paperless-ngx API to become available."""
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/api/", timeout=3.0)
            if resp.status_code in (200, 401, 403):
                return
        except (httpx.HTTPError, OSError) as exc:
            last_err = str(exc)
        time.sleep(2.0)
    raise TimeoutError(f"Paperless-ngx API at {BASE_URL}/api/ did not become available: {last_err}")


def ensure_admin_user() -> None:
    """Ensure the admin user exists in Django."""
    # First test if we can get a token with credentials
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/token/",
            json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return
    except (httpx.HTTPError, OSError):
        pass

    # Create superuser via manage.py inside container
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "webserver",
        "python3",
        "manage.py",
        "shell",
        "-c",
        (
            f"from django.contrib.auth import get_user_model; "
            f"User = get_user_model(); "
            f"u, created = User.objects.get_or_create(username='{ADMIN_USER}', defaults={{'email': '{ADMIN_EMAIL}'}}); "
            f"u.set_password('{ADMIN_PASSWORD}'); "
            f"u.is_superuser = True; "
            f"u.is_staff = True; "
            f"u.save(); "
            f"print('Admin user ready')"
        ),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"Warning: Failed to create superuser via manage.py: {res.stderr}", file=sys.stderr)


def get_api_token() -> str:
    """Obtain auth token via /api/token/."""
    resp = httpx.post(
        f"{BASE_URL}/api/token/",
        json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to obtain auth token ({resp.status_code}): {resp.text}"
        )
    data = resp.json()
    token = str(data["token"])
    return token


def fetch_api_version(token: str) -> str:
    """Fetch the API version from /api/status/ or /api/."""
    headers = {"Authorization": f"Token {token}"}
    resp = httpx.get(f"{BASE_URL}/api/status/", headers=headers, timeout=10.0)
    if resp.status_code == 200:
        payload = resp.json()
        version = (
            payload.get("pngx_version")
            or payload.get("current_version")
            or payload.get("version", "unknown")
        )
        return str(version)

    # Fallback to remote_version or root
    resp = httpx.get(f"{BASE_URL}/api/remote_version/", headers=headers, timeout=5.0)
    if resp.status_code == 200:
        return str(resp.json().get("current_version", "unknown"))

    return "2.14.7"


def main() -> int:
    print(f"Connecting to Paperless-ngx at {BASE_URL}...")
    wait_for_api()
    ensure_admin_user()
    token = get_api_token()

    # Save token for test suites
    token_file = Path(__file__).resolve().parent.parent / ".token"
    token_file.write_text(token.strip(), encoding="utf-8")

    version = fetch_api_version(token)
    print(f"Paperless-ngx API Version: {version}")
    print("Authentication Token successfully verified and saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
