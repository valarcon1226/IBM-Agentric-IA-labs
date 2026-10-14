"""Módulo de transcripción local con faster-whisper y extracción de audio con ffmpeg."""

import json
import logging
from pathlib import Path
import subprocess
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WordTiming(BaseModel):
    """Marca de tiempo por palabra."""
    word: str
    start: float
    end: float
    probability: float = 1.0


class TranscriptSegment(BaseModel):
    """Segmento de transcripción con marcas por palabra."""
    id: int
    start: float
    end: float
    text: str
    words: List[WordTiming] = Field(default_factory=list)


class Transcript(BaseModel):
    """Transcripción completa de un video o audio."""
    segments: List[TranscriptSegment] = Field(default_factory=list)
    language: str = "es"
    duration: float = 0.0

    @property
    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text)


def format_timestamp_srt(seconds: float) -> str:
    """Convierte segundos a formato SRT (HH:MM:SS,mmm)."""
    if seconds < 0:
        seconds = 0.0
    total_millis = int(round(seconds * 1000))
    hours = total_millis // 3_600_000
    remainder = total_millis % 3_600_000
    minutes = remainder // 60_000
    remainder = remainder % 60_000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def extract_audio(video_path: Path, output_audio_path: Optional[Path] = None) -> Path:
    """
    Extrae la pista de audio de un video a formato WAV 16kHz mono (optimizado para Whisper)
    usando ffmpeg.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")

    if output_audio_path is None:
        output_audio_path = video_path.with_suffix(".wav")
    else:
        output_audio_path = Path(output_audio_path)

    output_audio_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_audio_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Error extrayendo audio con ffmpeg: {result.stderr}")
        raise RuntimeError(f"Fallo al extraer audio del video: {result.stderr}")

    return output_audio_path


def transcribe_audio(
    audio_path: Path,
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    language: Optional[str] = None,
) -> Transcript:
    """
    Transcribe el audio usando faster-whisper con marcas de tiempo por palabra.
    Por defecto usa el modelo 'small' en CPU con cuantización int8 (óptimo para laptops).
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")

    from faster_whisper import WhisperModel

    logger.info(
        f"Iniciando transcripción con faster-whisper (modelo: {model_size}, device: {device}, compute_type: {compute_type})"
    )
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments_gen, info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language=language,
    )

    detected_language = info.language if hasattr(info, "language") else (language or "es")
    total_duration = info.duration if hasattr(info, "duration") else 0.0

    transcript_segments: List[TranscriptSegment] = []
    seg_id = 0
    for segment in segments_gen:
        words: List[WordTiming] = []
        if segment.words:
            for w in segment.words:
                words.append(
                    WordTiming(
                        word=w.word.strip(),
                        start=round(w.start, 3),
                        end=round(w.end, 3),
                        probability=round(w.probability, 3) if hasattr(w, "probability") else 1.0,
                    )
                )

        transcript_segments.append(
            TranscriptSegment(
                id=seg_id,
                start=round(segment.start, 3),
                end=round(segment.end, 3),
                text=segment.text.strip(),
                words=words,
            )
        )
        seg_id += 1

    if not total_duration and transcript_segments:
        total_duration = transcript_segments[-1].end

    return Transcript(
        segments=transcript_segments,
        language=detected_language,
        duration=round(total_duration, 3),
    )


def save_transcript_json(transcript: Transcript, output_path: Path) -> Path:
    """Guarda la transcripción completa con palabras en un archivo JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(transcript.model_dump_json(indent=2))
    return output_path


def load_transcript_json(json_path: Path) -> Transcript:
    """Carga un transcript.json existente."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Transcript.model_validate(data)


def save_transcript_srt(transcript: Transcript, output_path: Path) -> Path:
    """Exporta los segmentos a formato SubRip (.srt)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for idx, seg in enumerate(transcript.segments, start=1):
        lines.append(str(idx))
        start_srt = format_timestamp_srt(seg.start)
        end_srt = format_timestamp_srt(seg.end)
        lines.append(f"{start_srt} --> {end_srt}")
        lines.append(seg.text)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path
