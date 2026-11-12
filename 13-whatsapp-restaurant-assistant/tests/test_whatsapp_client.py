"""Unit tests for app.whatsapp (DECISIONES-13 W4) using httpx.MockTransport.

No real network call is ever made.
"""

import httpx
import pytest

from app import whatsapp


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_send_text_single_message_success():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out1"}]})

    responses = await whatsapp.send_text("573001234567", "Hola", client=_client(handler))
    assert len(responses) == 1
    assert responses[0].status_code == 200
    assert len(calls) == 1
    body = calls[0].read()
    assert b'"to":"573001234567"' in body
    assert b'"type":"text"' in body


async def test_send_text_splits_long_text_into_multiple_messages():
    long_text = "a" * 9000  # 3 chunks of <=4096

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    responses = await whatsapp.send_text("573001234567", long_text, client=_client(handler))
    assert len(responses) == 3
    assert len(calls) == 3
    for call in calls:
        assert len(call.read()) < 4096 + 300  # body includes JSON overhead, still well under


def test_split_text_respects_limit():
    chunks = whatsapp.split_text("a" * 9000)
    assert len(chunks) == 3
    assert all(len(chunk) <= whatsapp.MAX_TEXT_LENGTH for chunk in chunks)
    assert "".join(chunks) == "a" * 9000


def test_split_text_short_text_single_chunk():
    assert whatsapp.split_text("hola") == ["hola"]


async def test_send_text_retries_on_429_then_succeeds():
    responses_sequence = [httpx.Response(429), httpx.Response(200, json={"messages": []})]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses_sequence.pop(0)

    monkeypatched_sleep_calls = []

    async def fake_sleep(seconds):
        monkeypatched_sleep_calls.append(seconds)

    original_sleep = whatsapp.asyncio.sleep
    whatsapp.asyncio.sleep = fake_sleep
    try:
        responses = await whatsapp.send_text("573001234567", "hola", client=_client(handler))
    finally:
        whatsapp.asyncio.sleep = original_sleep

    assert responses[0].status_code == 200
    assert len(monkeypatched_sleep_calls) == 1


async def test_send_text_retries_on_500_then_succeeds():
    responses_sequence = [httpx.Response(503), httpx.Response(200, json={"messages": []})]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses_sequence.pop(0)

    async def fake_sleep(seconds):
        return None

    original_sleep = whatsapp.asyncio.sleep
    whatsapp.asyncio.sleep = fake_sleep
    try:
        responses = await whatsapp.send_text("573001234567", "hola", client=_client(handler))
    finally:
        whatsapp.asyncio.sleep = original_sleep

    assert responses[0].status_code == 200


async def test_send_text_does_not_retry_on_400():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"error": "bad request"})

    responses = await whatsapp.send_text("573001234567", "hola", client=_client(handler))
    assert responses[0].status_code == 400
    assert len(calls) == 1  # no retry attempted


async def test_send_text_gives_up_after_max_attempts():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    async def fake_sleep(seconds):
        return None

    original_sleep = whatsapp.asyncio.sleep
    whatsapp.asyncio.sleep = fake_sleep
    try:
        responses = await whatsapp.send_text("573001234567", "hola", client=_client(handler))
    finally:
        whatsapp.asyncio.sleep = original_sleep

    assert responses[0].status_code == 500
    assert len(calls) == whatsapp._MAX_ATTEMPTS


async def test_send_template_builds_expected_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"messages": [{"id": "wamid.tpl"}]})

    response = await whatsapp.send_template(
        "573001234567", "order_confirmation", "es_CO", ["Juan", "34000"], client=_client(handler)
    )
    assert response.status_code == 200
    body = captured["body"]
    assert b'"name":"order_confirmation"' in body
    assert b'"code":"es_CO"' in body
    assert b'"text":"Juan"' in body


async def test_send_template_without_params_has_no_components():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"messages": []})

    await whatsapp.send_template(
        "573001234567", "hello_world", "en_US", [], client=_client(handler)
    )
    assert b"components" not in captured["body"]


@pytest.mark.parametrize(
    ("wa_id", "expected"),
    [("573001234567", "57300***4567")],
)
def test_mask_wa_id_reexported(wa_id, expected):
    from app.security import mask_wa_id

    assert mask_wa_id(wa_id) == expected
