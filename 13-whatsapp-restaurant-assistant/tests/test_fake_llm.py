"""Unit tests for app.fake_llm (DECISIONES-13 W6/W10): the scripted fake used when LLM_FAKE=true,
tested directly (not via a real HTTP round trip) since it's pure Python logic.
"""

import json

from app import fake_llm


async def test_plain_text_gets_canned_greeting():
    turn = await fake_llm.complete([{"role": "user", "content": "hola"}], [])
    assert turn.content == fake_llm.GREETING_REPLY
    assert turn.tool_calls == []


async def test_json_script_issues_the_named_tool_call():
    script = {"tool": "get_menu", "arguments": {}}
    turn = await fake_llm.complete([{"role": "user", "content": json.dumps(script)}], [])
    assert turn.content is None
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "get_menu"
    assert turn.tool_calls[0].arguments == {}


async def test_successful_tool_result_is_summarized():
    messages = [
        {"role": "user", "content": json.dumps({"tool": "get_menu", "arguments": {}})},
        {"role": "assistant", "content": None, "tool_calls": []},
        {"role": "tool", "tool_call_id": "x", "content": json.dumps({"dishes": []})},
    ]
    turn = await fake_llm.complete(messages, [])
    assert "Listo" in turn.content
    assert turn.tool_calls == []


async def test_tool_error_is_apologized():
    messages = [
        {"role": "user", "content": json.dumps({"tool": "get_order_status", "arguments": {}})},
        {
            "role": "tool",
            "tool_call_id": "x",
            "content": json.dumps({"error": "order_not_found", "message": "No existe ese pedido."}),
        },
    ]
    turn = await fake_llm.complete(messages, [])
    assert "No pude completarlo" in turn.content
    assert "No existe ese pedido." in turn.content


async def test_malformed_json_falls_back_to_greeting():
    turn = await fake_llm.complete([{"role": "user", "content": "{not json"}], [])
    assert turn.content == fake_llm.GREETING_REPLY
