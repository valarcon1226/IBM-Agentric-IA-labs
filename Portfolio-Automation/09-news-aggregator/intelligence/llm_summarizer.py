"""LLM summarizer module with resilient fallback to text extraction."""

import logging
import re

import httpx

logger = logging.getLogger(__name__)


def extract_fallback_summary(text: str, title: str = "") -> str:
    """Extracts 2-3 clean bullet points directly from text when LLM fails or times out."""
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = [s.strip() for s in re.split(r"[.\n]+", clean) if len(s.strip()) > 15]

    bullets = []
    for s in sentences[:3]:
        bullets.append(f"- {s}.")

    if not bullets and title:
        bullets.append(f"- {title.strip()}.")
        bullets.append("- Extracto editorial resumido directamente del artículo original.")

    if not bullets:
        bullets.append("- Resumen no disponible para este artículo.")

    return "\n".join(bullets)


def summarize(
    text: str,
    title: str = "",
    provider: str = "ollama",
    base_url: str = "http://fake_llm:8080/v1",
    model: str = "llama3:8b",
    api_key: str = "none",
    timeout: float = 4.0,
) -> str:
    """Summarizes an article into bullet points using an OpenAI-compatible endpoint with fallback."""
    clean_text = text[:3000].strip()
    if not clean_text:
        return extract_fallback_summary("", title=title)

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key and api_key != "none":
        headers["Authorization"] = f"Bearer {api_key}"

    prompt = (
        "Eres un analista de inteligencia tecnológica. Genera un resumen ejecutivo "
        "de 2 o 3 viñetas concisas en español sobre el siguiente artículo:\n\n"
        f"Título: {title}\n"
        f"Contenido: {clean_text}\n\n"
        "Responde exclusivamente con las viñetas en formato:\n"
        "- Viñeta 1\n- Viñeta 2\n- Viñeta 3"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Eres un asistente de síntesis periodística."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 250,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content and content.strip():
                        return content.strip()
            logger.warning(f"LLM request returned status {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.info(f"LLM summarizer fallback activated (cause: {exc})")

    # Resilient fallback
    return extract_fallback_summary(clean_text, title=title)
