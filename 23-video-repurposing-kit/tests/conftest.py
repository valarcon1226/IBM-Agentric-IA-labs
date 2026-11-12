"""Configuración global y fixtures para la suite de pruebas del Video Repurposing Kit."""

import math
from pathlib import Path
import struct
import subprocess
import wave
import pytest

from kit.moments import HighlightSegment, HighlightsCollection
from kit.transcriber import Transcript, TranscriptSegment, WordTiming


@pytest.fixture(scope="session")
def test_video_path(tmp_path_factory) -> Path:
    """
    Genera un video de prueba de 2 minutos (120 s) a 1920x1080 25fps con ffmpeg
    y audio sintético con cadencia de voz humana (pausas y armónicos).
    Reutilizado en toda la sesión de pruebas.
    """
    root_dir = Path(__file__).resolve().parent.parent
    local_video = root_dir / "test_video_2min.mp4"

    if local_video.exists():
        return local_video

    # Generar audio sintético de 120s
    temp_dir = tmp_path_factory.mktemp("media")
    wav_path = temp_dir / "synth_voice.wav"
    sample_rate = 16000
    duration = 120
    num_samples = sample_rate * duration

    with wave.open(str(wav_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            phrase_time = t % 4.0
            if phrase_time < 2.8:
                envelope = math.sin(phrase_time * 8 * math.pi) ** 2
                val = (
                    math.sin(2 * math.pi * 150 * t)
                    + 0.5 * math.sin(2 * math.pi * 300 * t)
                    + 0.3 * math.sin(2 * math.pi * 600 * t)
                ) * envelope
                sample = int(val * 10000)
            else:
                sample = 0
            frames.extend(struct.pack("<h", max(-32767, min(32767, sample))))
        wf.writeframes(frames)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=120:size=1920x1080:rate=25",
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        str(local_video),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Fallo al generar video de prueba: {res.stderr}")

    return local_video


@pytest.fixture
def sample_transcript() -> Transcript:
    """Fixture de transcripción de 120s realista con marcas de palabra."""
    script_segments = [
        (0.0, 15.0, "Bienvenidos al episodio de hoy sobre cómo crear clips virales en redes sociales."),
        (15.0, 38.0, "El error más grande que comete la gente es subir videos horizontales sin subtítulos atractivos."),
        (38.0, 68.0, "La clave para retener la atención es colocar un gancho en los primeros tres segundos y subtítulos con palabras resaltadas."),
        (68.0, 95.0, "Cuando aplicas este método de recorte vertical 9:16, tus reproducciones pueden multiplicarse por diez."),
        (95.0, 120.0, "En resumen, automatizar la reutilización de contenido te ahorra horas de trabajo cada semana."),
    ]

    segments = []
    for idx, (st, en, text) in enumerate(script_segments):
        words_list = text.split()
        dur_per_word = (en - st) / len(words_list)
        words = []
        cur = st
        for w in words_list:
            words.append(
                WordTiming(
                    word=w,
                    start=round(cur, 3),
                    end=round(cur + dur_per_word, 3),
                    probability=0.98,
                )
            )
            cur += dur_per_word
        segments.append(
            TranscriptSegment(
                id=idx,
                start=st,
                end=en,
                text=text,
                words=words,
            )
        )

    return Transcript(
        segments=segments,
        language="es",
        duration=120.0,
    )


@pytest.fixture
def sample_highlights() -> HighlightsCollection:
    """Fixture de momentos virales destacados."""
    return HighlightsCollection(
        video_file="test_video_2min.mp4",
        highlights=[
            HighlightSegment(
                id=1,
                start=15.0,
                end=40.0,
                duration=25.0,
                title="El error más común en video",
                hook="El error más grande que comete la gente es subir videos sin subtítulos.",
                score=9.2,
                reason="Identifica un error frecuente de alto interés.",
            ),
            HighlightSegment(
                id=2,
                start=38.0,
                end=68.0,
                duration=30.0,
                title="El secreto para retener audiencia",
                hook="La clave para retener la atención es colocar un gancho en los primeros tres segundos.",
                score=9.6,
                reason="Consejo práctico de retención.",
            ),
        ],
    )
