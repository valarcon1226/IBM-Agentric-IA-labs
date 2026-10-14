"""Minimal OpenAI-compatible chat-completions server for local dev/tests (DECISIONES-14 A2/A4).

Stdlib only (``http.server``) — no dependency, no Dockerfile base image beyond ``python:3.12-slim``.
Deterministic: never calls a real LLM. Dispatches on a ``TAREA: ...`` marker that the calling
n8n workflow puts at the top of its prompt, so parsing is a couple of regexes, not a model:

- ``TAREA: FACTURA``: extracts proveedor/NIT/fecha/subtotal/IVA/total/items from the invoice text
  in the prompt and returns them as a JSON string (what F2 expects back from a real LLM).
- ``TAREA: REPORTE_DIARIO``: returns a fixed Spanish sentence that repeats the dish names and
  amounts found in the prompt (what F3 expects back).
- anything else: a generic fixed reply, so the endpoint never 500s on an unexpected prompt.

Not a security boundary: it never validates the ``Authorization`` header n8n sends (the
Header Auth credential exists so the *workflow* exercises the real pattern; this double is just a
deterministic stand-in for OmniRoute/Groq/OpenAI in production, per A4).
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8000

PROVEEDOR_RE = re.compile(r"Proveedor:\s*(.+)")
NIT_RE = re.compile(r"NIT:\s*(.+)")
FECHA_RE = re.compile(r"Fecha:\s*(.+)")
SUBTOTAL_RE = re.compile(r"Subtotal:\s*(\d+)")
IVA_RE = re.compile(r"IVA:\s*(\d+)")
TOTAL_RE = re.compile(r"Total:\s*(\d+)")
INVOICE_ITEM_RE = re.compile(r"^-\s*(.+?)\s+x\s+(\d+)\s*=\s*(\d+)\s*$", re.MULTILINE)

SALE_ITEM_RE = re.compile(r"^-\s*(.+?):\s*(\d+)\s*unidades?,\s*\$(\d+)\s*$", re.MULTILINE)
TOTAL_DIA_RE = re.compile(r"Total del d[ií]a:\s*\$(\d+)")


def _group_or_none(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _int_or_none(pattern: re.Pattern, text: str) -> int | None:
    match = pattern.search(text)
    return int(match.group(1)) if match else None


def extract_invoice(text: str) -> dict:
    items = [
        {"nombre": nombre.strip(), "cantidad": int(cantidad), "precio": int(precio)}
        for nombre, cantidad, precio in INVOICE_ITEM_RE.findall(text)
    ]
    return {
        "proveedor": _group_or_none(PROVEEDOR_RE, text),
        "nit": _group_or_none(NIT_RE, text),
        "fecha": _group_or_none(FECHA_RE, text),
        "subtotal": _int_or_none(SUBTOTAL_RE, text),
        "iva": _int_or_none(IVA_RE, text),
        "total": _int_or_none(TOTAL_RE, text),
        "items": items,
    }


def build_daily_summary(text: str) -> str:
    fecha = _group_or_none(FECHA_RE, text) or "ayer"
    items = SALE_ITEM_RE.findall(text)
    total_match = TOTAL_DIA_RE.search(text)
    total = total_match.group(1) if total_match else None

    if items:
        parts = [
            f"{cantidad} unidades de {nombre} (${monto} COP)" for nombre, cantidad, monto in items
        ]
        detalle = "; ".join(parts)
    else:
        detalle = "sin ventas registradas"

    summary = f"Resumen de ventas de Sabor de Casa del {fecha}: se vendieron {detalle}."
    if total:
        summary += f" Total del día: ${total} COP."
    summary += " ¡Buen trabajo, equipo!"
    return summary


def build_reply_content(prompt_text: str) -> str:
    if "TAREA: FACTURA" in prompt_text:
        return json.dumps(extract_invoice(prompt_text), ensure_ascii=False)
    if "TAREA: REPORTE_DIARIO" in prompt_text:
        return build_daily_summary(prompt_text)
    return "No reconozco esta tarea (fake-llm): revisa el marcador TAREA: en el prompt."


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            request = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": f"invalid request body: {exc}"})
            return

        messages = request.get("messages") or []
        prompt_text = "\n".join(str(m.get("content", "")) for m in messages)
        content = build_reply_content(prompt_text)

        self._send_json(
            200,
            {
                "id": "fake-llm-0001",
                "object": "chat.completion",
                "model": request.get("model", "fake-llm"),
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )

    def log_message(self, format: str, *args) -> None:  # noqa: A002 (stdlib signature)
        pass  # keep container logs quiet; errors already return a JSON body


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[fake-llm] listening on :{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
