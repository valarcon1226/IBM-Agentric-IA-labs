"""Unit tests for app.conversation (DECISIONES-13 W4): dedupe, rate limit, handler orchestration.

The database functions (`mark_processed`, `record_message`, `check_rate_limit`) are monkeypatched
with in-memory fakes so these tests never touch a real Postgres — that is covered by the
integration/E2E suite against the real docker compose stack.
"""

import pytest

from app import conversation

FAKE_AGENT_REPLY = "respuesta del agente (fake)"


@pytest.fixture
def no_op_record(monkeypatch):
    calls = []

    async def fake_record_message(wa_id, role, content):
        calls.append((wa_id, role, content))

    monkeypatch.setattr(conversation, "record_message", fake_record_message)
    return calls


@pytest.fixture(autouse=True)
def fake_agent(monkeypatch):
    async def fake_run_agent(wa_id, text):
        return [FAKE_AGENT_REPLY]

    monkeypatch.setattr(conversation, "run_agent", fake_run_agent)


@pytest.fixture(autouse=True)
def not_paused_by_default(monkeypatch):
    """Every pre-existing test in this module exercises a customer with no active handover."""

    async def fake_is_handover_active(wa_id):
        return False

    monkeypatch.setattr(conversation, "is_handover_active", fake_is_handover_active)


async def test_dedupe_skips_already_processed_message(monkeypatch, no_op_record):
    seen = {"wamid.1"}

    async def fake_mark_processed(message_id):
        if message_id in seen:
            return False
        seen.add(message_id)
        return True

    async def fake_check_rate_limit(wa_id):
        return True, False

    monkeypatch.setattr(conversation, "mark_processed", fake_mark_processed)
    monkeypatch.setattr(conversation, "check_rate_limit", fake_check_rate_limit)

    replies = await conversation.process_incoming_message("573001234567", "wamid.1", "text", "hola")
    assert replies == []
    assert no_op_record == []  # never persisted: it's a duplicate


async def test_new_message_id_is_processed(monkeypatch, no_op_record):
    async def fake_mark_processed(message_id):
        return True

    async def fake_check_rate_limit(wa_id):
        return True, False

    monkeypatch.setattr(conversation, "mark_processed", fake_mark_processed)
    monkeypatch.setattr(conversation, "check_rate_limit", fake_check_rate_limit)

    replies = await conversation.process_incoming_message("573001234567", "wamid.2", "text", "hola")
    assert replies == [FAKE_AGENT_REPLY]
    assert ("573001234567", "customer", "hola") in no_op_record
    assert ("573001234567", "assistant", FAKE_AGENT_REPLY) in no_op_record


async def test_non_text_message_gets_polite_reply(monkeypatch, no_op_record):
    async def fake_mark_processed(message_id):
        return True

    async def fake_check_rate_limit(wa_id):
        return True, False

    monkeypatch.setattr(conversation, "mark_processed", fake_mark_processed)
    monkeypatch.setattr(conversation, "check_rate_limit", fake_check_rate_limit)

    replies = await conversation.process_incoming_message("573001234567", "wamid.3", "image", None)
    assert replies == [conversation.NON_TEXT_REPLY]
    assert ("573001234567", "customer", "[image]") in no_op_record


async def test_rate_limit_exceeded_sends_one_warning(monkeypatch, no_op_record):
    async def fake_mark_processed(message_id):
        return True

    async def fake_check_rate_limit(wa_id):
        return False, True  # just crossed the limit

    monkeypatch.setattr(conversation, "mark_processed", fake_mark_processed)
    monkeypatch.setattr(conversation, "check_rate_limit", fake_check_rate_limit)

    replies = await conversation.process_incoming_message("573001234567", "wamid.4", "text", "hola")
    assert replies == [conversation.RATE_LIMIT_REPLY]


async def test_rate_limit_still_exceeded_stays_silent(monkeypatch, no_op_record):
    async def fake_mark_processed(message_id):
        return True

    async def fake_check_rate_limit(wa_id):
        return False, False  # already warned, still over the limit

    monkeypatch.setattr(conversation, "mark_processed", fake_mark_processed)
    monkeypatch.setattr(conversation, "check_rate_limit", fake_check_rate_limit)

    replies = await conversation.process_incoming_message("573001234567", "wamid.5", "text", "hola")
    assert replies == []


async def test_dev_chat_without_message_id_is_never_deduped(monkeypatch, no_op_record):
    calls = []

    async def fake_mark_processed(message_id):
        calls.append(message_id)
        return True

    async def fake_check_rate_limit(wa_id):
        return True, False

    monkeypatch.setattr(conversation, "mark_processed", fake_mark_processed)
    monkeypatch.setattr(conversation, "check_rate_limit", fake_check_rate_limit)

    await conversation.process_incoming_message("573001234567", None, "text", "hola")
    assert calls == []  # mark_processed was never called: no message_id to dedupe


async def test_handle_incoming_delegates_to_the_agent():
    replies = await conversation.handle_incoming("573001234567", "cualquier cosa")
    assert replies == [FAKE_AGENT_REPLY]


# --- W7: bot pause / staff commands --------------------------------------------------------


async def test_handle_incoming_stays_silent_while_handover_is_active(monkeypatch):
    async def fake_is_handover_active(wa_id):
        return True

    monkeypatch.setattr(conversation, "is_handover_active", fake_is_handover_active)

    replies = await conversation.handle_incoming("573001234567", "¿siguen ahí?")
    assert replies == []


async def test_handle_incoming_routes_staff_command_for_staff_number(monkeypatch):
    def fake_is_staff(wa_id):
        return wa_id == "573009999999"

    monkeypatch.setattr(conversation, "is_staff", fake_is_staff)

    calls = []

    async def fake_handle_staff_command(staff_wa_id, text):
        calls.append((staff_wa_id, text))
        return ["ok"]

    monkeypatch.setattr(conversation, "handle_staff_command", fake_handle_staff_command)

    replies = await conversation.handle_incoming("573009999999", "/pedidos")
    assert replies == ["ok"]
    assert calls == [("573009999999", "/pedidos")]


async def test_handle_incoming_treats_slash_command_from_non_staff_as_normal_customer():
    """A random customer typing `/algo` is not staff: it goes to the agent like any other text."""
    replies = await conversation.handle_incoming("573001234567", "/no-soy-personal")
    assert replies == [FAKE_AGENT_REPLY]


async def test_handle_incoming_staff_number_without_slash_is_a_normal_customer(monkeypatch):
    def fake_is_staff(wa_id):
        return wa_id == "573009999999"

    monkeypatch.setattr(conversation, "is_staff", fake_is_staff)

    replies = await conversation.handle_incoming("573009999999", "hola, quiero un domicilio")
    assert replies == [FAKE_AGENT_REPLY]
