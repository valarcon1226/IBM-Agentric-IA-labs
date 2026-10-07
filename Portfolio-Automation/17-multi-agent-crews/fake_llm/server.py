"""Deterministic OpenAI-compatible LLM for tests and the docker demo (stdlib only).

Behaviour per request:
- tools offered and the last message is not a tool result -> call the first tool with sensible arguments;
- the system prompt is the reviewer's -> the final Markdown report (+ TERMINATE for AutoGen);
- anything else -> a short note that quotes the tool result, so data flows between agents.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPORT = """# Demanda de agentes de IA en LATAM

## Hallazgos
- Las vacantes que piden CrewAI o AutoGen pasaron de 1.200 a 3.600 en un año (+200%) [doc_03.md].
- El 62% de las pymes encuestadas quiere automatizar la atención por WhatsApp [doc_01.md].

## Recomendaciones
- Priorizar un producto de agentes para atención al cliente por WhatsApp.
- Ofrecer despliegue gestionado: es lo que más cuesta a las pymes.

## Fuentes
- doc_01.md
- doc_03.md
"""


def _text(content) -> str:
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def reply(body: dict) -> dict:
    messages = body.get("messages", [])
    system = " ".join(_text(m.get("content")) for m in messages if m.get("role") == "system")
    last = messages[-1] if messages else {}
    tools = body.get("tools") or []
    message: dict = {"role": "assistant", "content": None}

    if tools and last.get("role") != "tool":
        name = tools[0]["function"]["name"]
        topic = re.sub(r"\s+", " ", _text(messages[1].get("content") if len(messages) > 1 else ""))[:120]
        args = {"expression": "(3600-1200)/1200"} if "calc" in name else {"query": topic or "agentes IA LATAM"}
        message["tool_calls"] = [
            {
                "id": f"call_{len(messages)}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ]
        finish = "tool_calls"
    else:
        if "Revisor" in system:
            content = REPORT + ("\nTERMINATE" if "TERMINATE" in system else "")
        else:
            tool_out = next((_text(m.get("content")) for m in reversed(messages) if m.get("role") == "tool"), "")
            content = f"Notas: {tool_out[:300] or 'sin datos nuevos'}"
            if "Final Answer" in system:  # CrewAI's text protocol, if it ever falls back to it
                content = "Final Answer: " + content
        message["content"] = content
        finish = "stop"
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "created": 0,
        "model": body.get("model", "fake"),
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        self._send(200, {"status": "ok"} if self.path == "/health" else {"object": "list", "data": []})

    def do_POST(self):  # noqa: N802
        if not self.path.endswith("/chat/completions"):
            return self._send(404, {"error": "not found"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self._send(200, reply(body))

    def log_message(self, *args):  # quiet
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()
