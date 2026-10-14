"""Pruebas unitarias para kit/subtitles.py."""


from kit.subtitles import (
    extract_words_for_clip,
    format_ass_time,
    generate_ass_subtitles,
)
from kit.transcriber import WordTiming


def test_format_ass_time():
    """Valida formato de marcas de tiempo ASS (H:MM:SS.cc)."""
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(1.25) == "0:00:01.25"
    assert format_ass_time(65.8) == "0:01:05.80"
    assert format_ass_time(3600.0) == "1:00:00.00"


def test_extract_words_for_clip(sample_transcript):
    """Verifica el filtrado de palabras para el intervalo del clip."""
    clip_words = extract_words_for_clip(sample_transcript, start=15.0, end=38.0)
    assert len(clip_words) > 0
    assert clip_words[0].start >= 15.0
    assert clip_words[-1].end <= 38.0 + 0.1
    # Primera palabra del segmento
    assert "error" in [w.word.lower() for w in clip_words]


def test_generate_ass_subtitles(tmp_path):
    """Verifica que el archivo ASS incluya encabezados 1080x1920 y resaltado de palabras."""
    words = [
        WordTiming(word="Este", start=1.0, end=1.5),
        WordTiming(word="es", start=1.5, end=1.8),
        WordTiming(word="el", start=1.8, end=2.0),
        WordTiming(word="secreto", start=2.0, end=2.8),
    ]
    ass_path = tmp_path / "subtitles.ass"
    res = generate_ass_subtitles(
        words=words,
        clip_start=1.0,
        clip_end=3.0,
        output_path=ass_path,
        words_per_line=4,
    )

    assert res == ass_path
    assert ass_path.exists()
    content = ass_path.read_text(encoding="utf-8")

    # Comprobar resolución vertical de lienzo
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content

    # Comprobar estilos Reels
    assert "Style: ReelsDefault" in content
    assert "Dialogue: 0," in content

    # Comprobar que contiene la etiqueta de color para palabra resaltada
    assert "{\\c&H0000FFFF&\\b1}SECRETO{\\c&H00FFFFFF&\\b1}" in content
