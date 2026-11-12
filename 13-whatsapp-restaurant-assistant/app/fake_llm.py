"""Scripted fake LLM (DECISIONES-13 W6/W10), used only when `LLM_FAKE=true`: unit tests and local
`/dev/chat` demos run without a real model, documented as test-only in `.env.example`/README.

The simulated customer message IS the script: a JSON object like
`{"tool": "create_order", "arguments": {...}}`. On the first turn the fake "decides" to call
exactly that tool; once the tool result comes back (as the following `tool`-role message) it
writes a short reply summarizing it, or apologizing if the tool returned an error. Plain text with
no such JSON gets a canned greeting reply — enough to exercise the history/retrieval wiring
end-to-end without scripting a tool call.
"""

import json
import uuid
from typing import Any

from app.llm_types import LLMTurn, ToolCall

GREETING_REPLY = (
    "¡Hola! Soy el asistente de Sabor de Casa (modo de prueba, LLM_FAKE=true). "
    "Dime en qué te ayudo."
)


def _last_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in reversed(messages):
        if message["role"] == "user":
            return message
    return None


async def complete(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
    last = messages[-1]

    if last["role"] == "tool":
        result = json.loads(last["content"])
        if "error" in result:
            return LLMTurn(content=f"No pude completarlo: {result.get('message', result['error'])}")
        return LLMTurn(content=f"Listo, aquí está el resultado: {json.dumps(result)}")

    user_message = _last_user_message(messages)
    if user_message is None:
        return LLMTurn(content=GREETING_REPLY)

    try:
        script = json.loads(user_message["content"])
    except (json.JSONDecodeError, TypeError):
        return LLMTurn(content=GREETING_REPLY)

    tool_name = script.get("tool")
    if not isinstance(tool_name, str):
        return LLMTurn(content=GREETING_REPLY)

    return LLMTurn(
        content=None,
        tool_calls=[
            ToolCall(
                id=f"fake-{uuid.uuid4().hex[:8]}",
                name=tool_name,
                arguments=script.get("arguments", {}),
            )
        ],
    )
