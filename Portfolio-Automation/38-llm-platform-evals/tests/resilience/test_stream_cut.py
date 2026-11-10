"""Resilience tests for premature stream interruption (stream cut mid-response).

Tests that a stream cut after 5 chunks without finish_reason or [DONE]
is never reported as a complete, successful answer:
- Layer 1: OpenAI Python SDK calling LiteLLM proxy
- Layer 2: Open WebUI's backend API (/api/chat/completions)
- Layer 3: Open WebUI user interface via Playwright on Microsoft Edge

Identifies and characterizes FINDING-002: LiteLLM synthesizes finish_reason='stop'
and [DONE] on connection termination, silently disguising stream cuts across all 3 layers.
"""

from __future__ import annotations

import os
import shutil
from typing import List

import httpx
import pytest
from openai import OpenAI

from tests.fake_upstream import FakeUpstreamServer


@pytest.fixture
def openwebui_auth_token(litellm_base_url: str) -> str:
    """Obtains a valid auth token from Open WebUI for API-level tests."""
    openwebui_url = os.getenv("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    signin_payload = {"email": "admin@example.com", "password": "AdminPassword123!"}
    try:
        resp = httpx.post(f"{openwebui_url}/api/v1/auths/signin", json=signin_payload, timeout=5.0)
        if resp.status_code == 200:
            token = str(resp.json().get("token", ""))
            if token:
                return token
    except Exception:
        pass

    # Fallback to signup if not signed in
    signup_payload = {
        "name": "Admin",
        "email": "admin@example.com",
        "password": "AdminPassword123!",
    }
    resp = httpx.post(f"{openwebui_url}/api/v1/auths/signup", json=signup_payload, timeout=5.0)
    assert resp.status_code == 200, f"Failed to authenticate with Open WebUI: {resp.text}"
    return str(resp.json()["token"])


@pytest.mark.resilience
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="FINDING-002: LiteLLM synthesizes finish_reason='stop' when upstream stream drops",
)
def test_stream_cut_layer1_openai_sdk(
    litellm_base_url: str,
    litellm_master_key: str,
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    """Layer 1: OpenAI SDK must detect an incomplete stream (exception or missing finish_reason)."""
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {
                    "status": 200,
                    "response_text": "One two three four five six seven eight nine ten",
                    "cut_after_chunks": 5,
                }
            ]
        },
        timeout=5.0,
    )

    client = OpenAI(base_url=f"{litellm_base_url}/v1", api_key=litellm_master_key)
    finish_reasons: List[str] = []
    received_content: List[str] = []

    try:
        stream = client.chat.completions.create(
            model="fake-fallback",
            messages=[{"role": "user", "content": "Test stream cut Layer 1"}],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                received_content.append(chunk.choices[0].delta.content)
            if chunk.choices and chunk.choices[0].finish_reason:
                finish_reasons.append(chunk.choices[0].finish_reason)
    except Exception:
        # If SDK raises an incomplete stream exception, that satisfies error detection
        return

    # If no exception was raised, finish_reason must NOT be 'stop'
    assert len(received_content) == 5, (
        f"Expected exactly 5 chunks before cut, got {len(received_content)}"
    )
    assert "stop" not in finish_reasons, (
        f"Expected missing/error finish_reason, but LiteLLM synthesized: {finish_reasons}"
    )


@pytest.mark.resilience
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="FINDING-002: Open WebUI API receives synthetic stop and reports success",
)
def test_stream_cut_layer2_openwebui_api(
    fake_upstream_server: FakeUpstreamServer,
    openwebui_auth_token: str,
) -> None:
    """Layer 2: Open WebUI API must surface an error or failed status on cut stream."""
    openwebui_url = os.getenv("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {
                    "status": 200,
                    "response_text": "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel",
                    "cut_after_chunks": 5,
                }
            ]
        },
        timeout=5.0,
    )

    headers = {
        "Authorization": f"Bearer {openwebui_auth_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "fake-fallback",
        "messages": [{"role": "user", "content": "Test stream cut Layer 2"}],
        "stream": True,
    }

    lines: List[str] = []
    has_error = False
    try:
        with httpx.Client(timeout=10.0) as client:
            with client.stream(
                "POST", f"{openwebui_url}/api/chat/completions", headers=headers, json=payload
            ) as resp:
                if resp.status_code != 200:
                    has_error = True
                for line in resp.iter_lines():
                    if line:
                        lines.append(line)
                        if "error" in line.lower() or "failed" in line.lower():
                            has_error = True
    except Exception:
        has_error = True

    # If upstream stream was cut, API must report an error or omission of finish_reason: stop
    finish_reason_stop_present = any('"finish_reason":"stop"' in line for line in lines)
    assert has_error or not finish_reason_stop_present, (
        f"Open WebUI API reported complete success with synthetic 'stop'. Lines: {lines}"
    )


@pytest.mark.resilience
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="FINDING-002: Open WebUI renders cut answer as complete without warning or retry banner",
)
def test_stream_cut_layer3_openwebui_edge_ui(
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    """Layer 3: Open WebUI UI on Edge must show a warning or retry banner for cut answers."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright not installed in environment")

    # Check for Edge browser availability
    has_msedge = shutil.which("msedge") is not None or os.path.exists(
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    )
    if not has_msedge:
        pytest.skip("Microsoft Edge is not installed on this host (run from laptop per rule 4)")

    httpx.post(f"{fake_upstream_server.base_url}/control/reset", timeout=5.0)
    httpx.post(
        f"{fake_upstream_server.base_url}/control/script",
        json={
            "behaviors": [
                {
                    "status": 200,
                    "response_text": "One two three four five six seven eight nine ten",
                    "cut_after_chunks": 5,
                }
            ]
        },
        timeout=5.0,
    )

    openwebui_url = os.getenv("OPENWEBUI_BASE_URL", "http://127.0.0.1:8088").rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"{openwebui_url}/", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # Dismiss onboarding modal if present
            try:
                lets_go = page.locator("button:has-text(\"Okay, Let's Go!\")")
                lets_go.wait_for(state="visible", timeout=4000)
                lets_go.click()
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Ensure model is fake-primary
            if page.locator("button:has-text('fake-primary')").count() == 0:
                model_btn = page.locator(
                    "button:has-text('primary-model'), button:has-text('Select a model')"
                )
                if model_btn.count() > 0:
                    model_btn.first.click()
                    page.wait_for_timeout(500)
                    fake_opt = page.locator(":text('fake-primary')")
                    if fake_opt.count() > 0:
                        fake_opt.first.click()
                        page.wait_for_timeout(500)

            chat_input = page.locator("#chat-input")
            chat_input.click()
            chat_input.fill("Simulate stream cut test layer 3")
            page.wait_for_timeout(500)
            chat_input.press("Enter")

            # Wait for generation to finish
            page.wait_for_timeout(5000)

            # Assert that the UI renders an error indicator or warning banner
            error_alerts = page.locator(
                "[role='alert'], .text-red-500, .bg-red-500, :text('Error'), :text('failed')"
            )
            assert error_alerts.count() > 0, (
                "Open WebUI rendered cut response as completely successful without warning banner"
            )
        finally:
            browser.close()
