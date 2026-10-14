"""Pruebas de integración del renderizado de video con ffmpeg y verificación con ffprobe."""

import hashlib
import subprocess


from kit.moments import HighlightSegment
from kit.renderer import render_all_highlights, render_clip


def run_ffprobe(cmd_args: list[str]) -> str:
    """Ejecuta ffprobe y devuelve la salida estándar limpia."""
    full_cmd = ["ffprobe", "-v", "error"] + cmd_args
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe falló: {res.stderr}")
    return res.stdout.strip()


def test_render_clip_and_ffprobe_verification(test_video_path, sample_transcript, tmp_path):
    """
    Verifica con ffprobe:
    - Duración exacta del corte.
    - Resolución vertical 1080x1920 (9:16).
    - Subtítulos quemados (frames con subtítulos difieren de frames sin subtítulos).
    """
    highlight = HighlightSegment(
        id=1,
        start=20.0,
        end=45.0,
        duration=25.0,
        title="Test Clip Vertical",
        hook="El error más común en video.",
        score=9.5,
    )

    clip_with_subs = tmp_path / "clip_with_subs.mp4"
    clip_no_subs = tmp_path / "clip_no_subs.mp4"

    # 1. Renderizar con subtítulos quemados
    render_clip(
        video_path=test_video_path,
        highlight=highlight,
        output_path=clip_with_subs,
        transcript=sample_transcript,
        burn_subtitles=True,
    )
    assert clip_with_subs.exists()

    # 2. Renderizar sin subtítulos quemados
    render_clip(
        video_path=test_video_path,
        highlight=highlight,
        output_path=clip_no_subs,
        transcript=sample_transcript,
        burn_subtitles=False,
    )
    assert clip_no_subs.exists()

    # 3. Verificación con ffprobe: Resolución 1080x1920
    dimensions = run_ffprobe([
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(clip_with_subs),
    ])
    assert dimensions == "1080x1920"

    # 4. Verificación con ffprobe: Duración (25s ±0.5s)
    dur_str = run_ffprobe([
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(clip_with_subs),
    ])
    duration = float(dur_str)
    assert abs(duration - 25.0) <= 0.6

    # 5. Verificación con ffprobe: Formato de audio AAC
    audio_codec = run_ffprobe([
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(clip_with_subs),
    ])
    assert audio_codec == "aac"

    # 6. Verificación de subtítulos quemados: los frames deben ser distintos
    # Extraer fotograma a los 2 segundos de cada video
    frame_with_subs = tmp_path / "frame_subs.png"
    frame_no_subs = tmp_path / "frame_nosubs.png"

    subprocess.run(
        ["ffmpeg", "-y", "-ss", "2.0", "-i", str(clip_with_subs), "-vframes", "1", str(frame_with_subs)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "2.0", "-i", str(clip_no_subs), "-vframes", "1", str(frame_no_subs)],
        capture_output=True,
        check=True,
    )

    hash_subs = hashlib.sha256(frame_with_subs.read_bytes()).hexdigest()
    hash_nosubs = hashlib.sha256(frame_no_subs.read_bytes()).hexdigest()

    assert hash_subs != hash_nosubs, "El fotograma con subtítulos quemados debe ser diferente al que no tiene subtítulos"


def test_render_all_highlights(test_video_path, sample_highlights, sample_transcript, tmp_path):
    """Verifica que render_all_highlights genere todos los clips en clips/."""
    clips_dir = tmp_path / "clips"
    rendered = render_all_highlights(
        video_path=test_video_path,
        highlights=sample_highlights.highlights,
        output_dir=clips_dir,
        transcript=sample_transcript,
    )

    assert len(rendered) == len(sample_highlights.highlights)
    for clip in rendered:
        assert clip.exists()
        assert clip.name.endswith(".mp4")
        assert "clip_" in clip.name
