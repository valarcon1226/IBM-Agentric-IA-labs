"""Pruebas unitarias para kit/transcriber.py."""

from unittest.mock import MagicMock, patch


from kit.transcriber import (
    extract_audio,
    format_timestamp_srt,
    load_transcript_json,
    save_transcript_json,
    save_transcript_srt,
    transcribe_audio,
    Transcript,
)


def test_format_timestamp_srt():
    """Valida formato SRT (HH:MM:SS,mmm)."""
    assert format_timestamp_srt(0.0) == "00:00:00,000"
    assert format_timestamp_srt(1.234) == "00:00:01,234"
    assert format_timestamp_srt(65.8) == "00:01:05,800"
    assert format_timestamp_srt(3661.05) == "01:01:01,050"


def test_save_and_load_transcript_json(sample_transcript, tmp_path):
    """Valida serialización y deserialización de transcript.json."""
    json_path = tmp_path / "transcript.json"
    save_transcript_json(sample_transcript, json_path)
    assert json_path.exists()

    loaded = load_transcript_json(json_path)
    assert len(loaded.segments) == len(sample_transcript.segments)
    assert loaded.duration == sample_transcript.duration
    assert loaded.segments[0].words[0].word == sample_transcript.segments[0].words[0].word


def test_save_transcript_srt(sample_transcript, tmp_path):
    """Valida formato y estructura del archivo .srt."""
    srt_path = tmp_path / "transcript.srt"
    save_transcript_srt(sample_transcript, srt_path)
    assert srt_path.exists()

    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:15,000" in content
    assert "Bienvenidos al episodio" in content
    assert "00:01:35,000 --> 00:02:00,000" in content


def test_extract_audio_ffmpeg(test_video_path, tmp_path):
    """Verifica que ffmpeg extraiga el audio a WAV 16kHz mono."""
    wav_out = tmp_path / "extracted_audio.wav"
    res = extract_audio(test_video_path, wav_out)
    assert res == wav_out
    assert wav_out.exists()
    assert wav_out.stat().st_size > 0


def test_transcribe_audio_mock(tmp_path):
    """Verifica el flujo de transcribe_audio usando un mock de WhisperModel."""
    fake_audio = tmp_path / "fake.wav"
    fake_audio.write_text("dummy")

    # Mock segment y palabras
    mock_word = MagicMock()
    mock_word.word = "Hola"
    mock_word.start = 0.5
    mock_word.end = 1.0
    mock_word.probability = 0.99

    mock_seg = MagicMock()
    mock_seg.start = 0.5
    mock_seg.end = 2.0
    mock_seg.text = "Hola mundo"
    mock_seg.words = [mock_word]

    mock_info = MagicMock()
    mock_info.language = "es"
    mock_info.duration = 2.0

    mock_model_inst = MagicMock()
    mock_model_inst.transcribe.return_value = ([mock_seg], mock_info)

    with patch("faster_whisper.WhisperModel", return_value=mock_model_inst):
        transcript = transcribe_audio(fake_audio, model_size="small")

        assert isinstance(transcript, Transcript)
        assert transcript.language == "es"
        assert len(transcript.segments) == 1
        assert transcript.segments[0].words[0].word == "Hola"
        assert transcript.segments[0].words[0].start == 0.5
