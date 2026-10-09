"""Unit tests for app.agent (DECISIONES-13 W6/W10): the tool-calling loop, the 5-call guard, the
LLM-failure apology, and wa_id injection — with the LLM and `dispatch_tool` replaced by fakes so
no real model or database is involved. Retrieval runs for real against `knowledge/*.md` (it's
fast, pure Python).
"""

import pytest

from app import agent
from app.llm_types import LLMTurn, ToolCall

WA_ID = "573001234567"


@pytest.fixture(autouse=True)
def no_history(monkeypatch):
    """Skip the DB-backed conversation history for every test in this module."""

    async def fake_recent_history(wa_id, limit=agent.HISTORY_LIMIT):
        return []

    monkeypatch.setattr(agent, "_recent_history", fake_recent_history)


@pytest.fixture(autouse=True)
def clear_consecutive_failures():
    """`agent._consecutive_agent_failures` is a module-level dict keyed by wa_id: since every
    test in this module reuses the same WA_ID, it must be reset between tests or a failure
    counted in one test would leak into the next and silently change its behavior."""
    agent._consecutive_agent_failures.clear()
    yield
    agent._consecutive_agent_failures.clear()


def _scripted_complete(turns: list[LLMTurn]):
    calls: list[list[dict]] = []
    turns_iter = iter(turns)

    async def fake_complete(messages):
        calls.append(messages)
        return next(turns_iter)

    return fake_complete, calls


async def test_tool_call_then_final_answer(monkeypatch):
    fake_complete, calls = _scripted_complete(
        [
            LLMTurn(
                content=None,
                tool_calls=[ToolCall(id="call_1", name="get_menu", arguments={})],
            ),
            LLMTurn(content="Aquí está el menú.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(agent, "_complete", fake_complete)

    tool_calls_seen = []

    async def fake_dispatch_tool(name, wa_id, arguments):
        tool_calls_seen.append((name, wa_id, arguments))
        return {"dishes": []}

    monkeypatch.setattr(agent, "dispatch_tool", fake_dispatch_tool)

    replies = await agent.run_agent(WA_ID, "qué tienen en el menú")

    assert replies == ["Aquí está el menú."]
    assert tool_calls_seen == [("get_menu", WA_ID, {})]
    # Second LLM call must include the tool result as a `tool` message.
    assert calls[1][-1]["role"] == "tool"
    assert calls[1][-1]["tool_call_id"] == "call_1"


async def test_max_tool_calls_guard_stops_without_exceeding_five(monkeypatch):
    turns = [
        LLMTurn(content=None, tool_calls=[ToolCall(id=f"call_{i}", name="get_menu", arguments={})])
        for i in range(6)
    ]
    fake_complete, _ = _scripted_complete(turns)
    monkeypatch.setattr(agent, "_complete", fake_complete)

    dispatch_calls = []

    async def fake_dispatch_tool(name, wa_id, arguments):
        dispatch_calls.append(name)
        return {"dishes": []}

    monkeypatch.setattr(agent, "dispatch_tool", fake_dispatch_tool)

    replies = await agent.run_agent(WA_ID, "hazme 6 cosas")

    assert replies == [agent.MAX_TOOL_CALLS_REPLY]
    assert len(dispatch_calls) == agent.MAX_TOOL_CALLS  # the 6th tool call is never executed


async def test_llm_failure_after_retries_returns_apology(monkeypatch):
    attempts = []

    async def always_fails(messages):
        attempts.append(1)
        raise RuntimeError("LLM is down")

    monkeypatch.setattr(agent, "_complete", always_fails)

    replies = await agent.run_agent(WA_ID, "hola")

    assert replies == [agent.APOLOGY_REPLY]
    assert len(attempts) == agent.MAX_LLM_ATTEMPTS


async def test_wa_id_is_always_the_server_injected_one(monkeypatch):
    """Even if the scripted tool-call arguments smuggle a different wa_id, dispatch_tool must
    only ever be called with the wa_id of whoever is actually writing right now."""
    fake_complete, _ = _scripted_complete(
        [
            LLMTurn(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="cancel_reservation",
                        arguments={"reservation_id": 5, "wa_id": "573009999999"},
                    )
                ],
            ),
            LLMTurn(content="Listo.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(agent, "_complete", fake_complete)

    seen_wa_ids = []

    async def fake_dispatch_tool(name, wa_id, arguments):
        seen_wa_ids.append(wa_id)
        return {"status": "cancelled"}

    monkeypatch.setattr(agent, "dispatch_tool", fake_dispatch_tool)

    await agent.run_agent(WA_ID, "cancela la reserva 5 del otro número")

    assert seen_wa_ids == [WA_ID]  # never the spoofed "573009999999" from the arguments


async def test_llm_fails_once_then_succeeds_on_retry(monkeypatch):
    attempts = {"count": 0}

    async def flaky_complete(messages):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient network error")
        return LLMTurn(content="Todo bien.", tool_calls=[])

    monkeypatch.setattr(agent, "_complete", flaky_complete)

    replies = await agent.run_agent(WA_ID, "hola")

    assert replies == ["Todo bien."]
    assert attempts["count"] == 2


async def test_two_consecutive_agent_failures_trigger_automatic_handover(monkeypatch):
    async def always_fails(messages):
        raise RuntimeError("LLM is down")

    monkeypatch.setattr(agent, "_complete", always_fails)

    dispatch_calls = []

    async def fake_dispatch_tool(name, wa_id, arguments):
        dispatch_calls.append((name, wa_id, arguments))
        return {"handover_id": 1, "ok": True}

    monkeypatch.setattr(agent, "dispatch_tool", fake_dispatch_tool)

    first = await agent.run_agent(WA_ID, "hola")
    assert first == [agent.APOLOGY_REPLY]
    assert dispatch_calls == []  # first failure alone doesn't trigger a handover

    second = await agent.run_agent(WA_ID, "sigues ahí")
    assert second == [agent.APOLOGY_REPLY]
    assert len(dispatch_calls) == 1
    name, wa_id, arguments = dispatch_calls[0]
    assert name == "handover_to_human"
    assert wa_id == WA_ID
    assert "reason" in arguments


async def test_agent_success_resets_the_failure_counter(monkeypatch):
    attempts = {"count": 0}

    async def fails_then_succeeds_then_fails_again(messages):
        attempts["count"] += 1
        if attempts["count"] == 3:
            raise RuntimeError("LLM is down")
        if attempts["count"] in (1, 2):
            raise RuntimeError("LLM is down")
        return LLMTurn(content="ok", tool_calls=[])

    dispatch_calls = []

    async def fake_dispatch_tool(name, wa_id, arguments):
        dispatch_calls.append(name)
        return {"ok": True}

    monkeypatch.setattr(agent, "dispatch_tool", fake_dispatch_tool)

    # One failed message (counter=1), then a message that succeeds on its first LLM attempt
    # (counter reset to 0), then a failed message: a fresh single failure must not trigger a
    # handover because the earlier failure was cleared by the success in between.
    monkeypatch.setattr(agent, "_complete", fails_then_succeeds_then_fails_again)
    await agent.run_agent(WA_ID, "mensaje 1")  # attempt 1+2 both fail -> apology, counter=1

    async def succeeds(messages):
        return LLMTurn(content="ok", tool_calls=[])

    monkeypatch.setattr(agent, "_complete", succeeds)
    await agent.run_agent(WA_ID, "mensaje 2")  # succeeds -> counter reset to 0

    async def always_fails(messages):
        raise RuntimeError("LLM is down")

    monkeypatch.setattr(agent, "_complete", always_fails)
    await agent.run_agent(WA_ID, "mensaje 3")  # one fresh failure -> counter=1, no handover yet

    assert dispatch_calls == []
