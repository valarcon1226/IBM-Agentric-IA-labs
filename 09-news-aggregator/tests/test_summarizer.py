"""Unit tests for LLM summarization and graceful degradation fallback."""

from unittest.mock import MagicMock, patch

import httpx

from intelligence.llm_summarizer import extract_fallback_summary, summarize


def test_extract_fallback_summary():
    text = (
        "La empresa presentó hoy su nueva tecnología. "
        "El sistema promete reducir los costos de operación un 40 por ciento. "
        "Las primeras pruebas piloto comenzarán el próximo mes en varias ciudades."
    )
    summary = extract_fallback_summary(text, title="Título de prueba")
    assert "- La empresa presentó hoy su nueva tecnología." in summary
    assert "- El sistema promete reducir los costos" in summary
    assert "\n- " in summary


def test_summarize_with_mocked_llm():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "- Anuncio de modelo avanzado.\n- Capacidades ampliadas de razonamiento.\n- Lanzamiento gradual.",
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        result = summarize("Texto largo del artículo", title="Título del artículo")
        assert "- Anuncio de modelo avanzado." in result
        assert "- Capacidades ampliadas de razonamiento." in result


def test_summarize_timeout_triggers_fallback():
    # Simulate network timeout
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timeout after 4s")):
        text = (
            "OpenAI lanzó GPT-5 con notables mejoras técnicas. "
            "El motor de inferencia resuelve ecuaciones complejas con facilidad. "
            "La API estará disponible a través de la plataforma oficial."
        )
        result = summarize(text, title="GPT-5 de OpenAI")
        # Assert fallback yielded bullet points extracted from body text
        assert result.startswith("- ")
        assert "OpenAI lanzó GPT-5" in result
