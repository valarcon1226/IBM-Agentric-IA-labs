"""Pruebas unitarias para kit/moments.py."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from kit.moments import (
    HighlightSegment,
    HighlightsCollection,
    load_highlights_json,
    save_highlights_json,
    select_moments_heuristic,
    select_moments_llm,
)


def test_highlight_segment_model():
    """Valida reglas del modelo Pydantic HighlightSegment."""
    seg = HighlightSegment(
        id=1,
        start=10.0,
        end=35.0,
        title="Consejo de Oro",
        hook="No hagas esto nunca.",
        score=9.5,
    )
    assert seg.duration == 25.0

    # Fin menor o igual que inicio debe fallar
    with pytest.raises(ValidationError):
        HighlightSegment(
            id=2,
            start=40.0,
            end=30.0,
            title="Inválido",
            hook="Hook",
            score=5.0,
        )


def test_select_moments_heuristic(sample_transcript):
    """Verifica que la selección heurística produzca segmentos válidos de 20-60s."""
    collection = select_moments_heuristic(sample_transcript, video_file="podcast.mp4")

    assert isinstance(collection, HighlightsCollection)
    assert len(collection.highlights) >= 2
    for h in collection.highlights:
        assert h.start >= 0.0
        assert h.end > h.start
        # Cada momento debe estar en el rango de 20 a 60 segundos
        assert 20.0 <= h.duration <= 60.0
        assert len(h.title) > 0
        assert len(h.hook) > 0
        assert 0.0 <= h.score <= 10.0


def test_select_moments_llm_success(sample_transcript):
    """Verifica la selección con un LLM falso que devuelve JSON compatible."""
    fake_llm_json = {
        "video_file": "podcast.mp4",
        "highlights": [
            {
                "id": 1,
                "start": 15.0,
                "end": 45.0,
                "duration": 30.0,
                "title": "El Gran Secreto de los Algoritmos",
                "hook": "La mayoría no entiende cómo funcionan los algoritmos hoy.",
                "score": 9.8,
                "reason": "Excelente enganche y revelación contundente.",
            },
            {
                "id": 2,
                "start": 60.0,
                "end": 90.0,
                "duration": 30.0,
                "title": "Aumenta tus Ventas con Reels",
                "hook": "Este cambio multiplicó mis ventas por diez.",
                "score": 9.5,
                "reason": "Historia de éxito motivacional.",
            },
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(fake_llm_json)}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_resp):
        res = select_moments_llm(
            sample_transcript,
            video_file="podcast.mp4",
            base_url="http://fake-llm/v1",
        )
        assert len(res.highlights) == 2
        assert res.highlights[0].title == "El Gran Secreto de los Algoritmos"
        assert res.highlights[0].duration == 30.0
        assert res.highlights[1].score == 9.5


def test_select_moments_llm_fallback_on_error(sample_transcript):
    """Verifica que si el LLM falla o está desconectado, se activa el modo heurístico."""
    with patch("httpx.Client.post", side_effect=Exception("Connection refused")):
        res = select_moments_llm(
            sample_transcript,
            video_file="podcast.mp4",
            base_url="http://offline-llm:11434/v1",
        )
        # Debe haber devuelto highlights por heurística sin explotar
        assert isinstance(res, HighlightsCollection)
        assert len(res.highlights) >= 2


def test_save_and_load_highlights_json(sample_highlights, tmp_path):
    """Verifica la persistencia y edición de highlights.json."""
    h_path = tmp_path / "highlights.json"
    save_highlights_json(sample_highlights, h_path)
    assert h_path.exists()

    loaded = load_highlights_json(h_path)
    assert len(loaded.highlights) == len(sample_highlights.highlights)
    assert loaded.highlights[0].title == sample_highlights.highlights[0].title

    # Simular edición manual del usuario (ej: cambiar inicio a 18.0)
    data = json.loads(h_path.read_text(encoding="utf-8"))
    data["highlights"][0]["start"] = 18.0
    data["highlights"][0]["title"] = "Título Editado Manualmente"
    h_path.write_text(json.dumps(data), encoding="utf-8")

    edited = load_highlights_json(h_path)
    assert edited.highlights[0].start == 18.0
    assert edited.highlights[0].title == "Título Editado Manualmente"
