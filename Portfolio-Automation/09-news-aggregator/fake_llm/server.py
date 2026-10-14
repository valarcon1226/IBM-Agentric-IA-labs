"""Deterministic OpenAI-compatible fake LLM server (stdlib only).

Provides:
- /health: Healthcheck endpoint.
- /v1/chat/completions: Deterministic bullet-point summarization.
- /v1/embeddings: Deterministic 768-dimensional embeddings for pgvector / Ollama nomic-embed-text.
"""

import hashlib
import json
import math
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _clean_text(content) -> str:
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content or "")


TOPIC_KEYWORDS = {
    "ai": ["openai", "gpt", "modelo", "razonamiento", "inteligencia", "artificial", "llm"],
    "sec": ["ransomware", "malware", "vulnerabilidad", "seguridad", "phishing", "ataque"],
    "cloud": ["kubernetes", "docker", "cloud", "devops", "servidores", "cluster"],
    "fin": ["acciones", "mercados", "bolsa", "bursatil", "inversion", "fintech"],
}


def _topic_vector(topic: str, dim: int) -> list[float]:
    import random
    rng = random.Random(int(hashlib.md5(topic.encode("utf-8")).hexdigest(), 16))
    return [rng.gauss(0, 1) for _ in range(dim)]


def generate_deterministic_embedding(text: str, dim: int = 768) -> list[float]:
    """Generates a deterministic unit-length vector with dense semantic alignment."""
    import random
    vec = [0.0] * dim
    words = re.findall(r"[a-zA-Z0-9_\-\.]{3,}", text.lower())
    if not words:
        vec[0] = 1.0
        return vec

    # Base word projections
    for w in words:
        rng = random.Random(int(hashlib.md5(w[:4].encode("utf-8")).hexdigest(), 16))
        for i in range(dim):
            vec[i] += rng.gauss(0, 1)

    # Semantic topic alignment
    clean_lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in clean_lower)
        if matches > 0:
            tv = _topic_vector(topic, dim)
            weight = matches * 3.5
            for i in range(dim):
                vec[i] += tv[i] * weight

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        return [round(x / norm, 6) for x in vec]
    vec[0] = 1.0
    return vec


def generate_summary(text: str) -> str:
    """Generates a concise 3-bullet summary in Spanish."""
    sentences = [s.strip() for s in re.split(r"[.\n]+", text) if len(s.strip()) > 15]
    if len(sentences) >= 3:
        bullets = [
            f"- {sentences[0]}.",
            f"- {sentences[1]}.",
            f"- {sentences[2]}.",
        ]
    elif len(sentences) == 2:
        bullets = [
            f"- {sentences[0]}.",
            f"- {sentences[1]}.",
            "- Cobertura adicional y seguimiento programado para las próximas horas.",
        ]
    elif len(sentences) == 1:
        bullets = [
            f"- {sentences[0]}.",
            "- Se destacan detalles clave y repercusiones en el sector tecnológico.",
            "- El equipo editorial continuará actualizando este reporte.",
        ]
    else:
        bullets = [
            "- Reporte y análisis de la novedad tecnológica del día.",
            "- Puntos clave sobre impacto en la industria y adopción.",
            "- Detalles técnicos recopilados desde las fuentes principales.",
        ]
    return "\n".join(bullets)


def handle_chat_completion(body: dict) -> dict:
    messages = body.get("messages", [])
    user_prompt = " ".join(_clean_text(m.get("content")) for m in messages if m.get("role") == "user")
    summary = generate_summary(user_prompt)

    return {
        "id": "chatcmpl-fake-news",
        "object": "chat.completion",
        "created": 1700000000,
        "model": body.get("model", "llama3:8b"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": summary},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
    }


def handle_embeddings(body: dict) -> dict:
    input_data = body.get("input", "")
    texts = [input_data] if isinstance(input_data, str) else list(input_data)
    data = []
    for i, t in enumerate(texts):
        embedding = generate_deterministic_embedding(str(t), dim=768)
        data.append({
            "object": "embedding",
            "index": i,
            "embedding": embedding,
        })

    return {
        "object": "list",
        "data": data,
        "model": body.get("model", "nomic-embed-text"),
        "usage": {"prompt_tokens": 20 * len(texts), "total_tokens": 20 * len(texts)},
    }


class FakeLLMHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path in ("/health", "/", "/v1/health"):
            self._send(200, {"status": "ok", "service": "fake_llm"})
        else:
            self._send(200, {"object": "list", "data": []})

    def do_POST(self):  # noqa: N802
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            body = {}

        if self.path.endswith("/chat/completions"):
            self._send(200, handle_chat_completion(body))
        elif self.path.endswith("/embeddings"):
            self._send(200, handle_embeddings(body))
        else:
            self._send(404, {"error": "Endpoint not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), FakeLLMHandler)
    print(f"Fake LLM server listening on port {port}")
    server.serve_forever()
