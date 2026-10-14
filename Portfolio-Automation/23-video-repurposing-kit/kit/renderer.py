"""Módulo de renderizado de video con ffmpeg: corte exacto, recorte 9:16, subtítulos ASS y audio normalizado."""

import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import List, Optional

from kit.moments import HighlightSegment
from kit.subtitles import extract_words_for_clip, generate_ass_subtitles
from kit.transcriber import Transcript

logger = logging.getLogger(__name__)


def slugify(text: str, max_words: int = 5) -> str:
    """Convierte un texto en un slug seguro para nombres de archivo."""
    # Quitar acentos y caracteres especiales
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    words = text.split()[:max_words]
    slug = "_".join(words)
    return slug or "clip"


def get_crop_offset(crop_mode: str = "center", x_offset: Optional[float] = None) -> float:
    """Calcula el factor de desplazamiento horizontal (0.0=izquierda, 0.5=centro, 1.0=derecha)."""
    if x_offset is not None:
        return max(0.0, min(1.0, float(x_offset)))
    crop_mode = crop_mode.lower().strip()
    if crop_mode == "left":
        return 0.0
    elif crop_mode == "right":
        return 1.0
    return 0.5  # default "center"


def render_clip(
    video_path: Path,
    highlight: HighlightSegment,
    output_path: Path,
    transcript: Optional[Transcript] = None,
    subtitles_ass_path: Optional[Path] = None,
    crop_mode: str = "center",
    x_offset: Optional[float] = None,
    burn_subtitles: bool = True,
) -> Path:
    """
    Renderiza un clip vertical 9:16 (1080x1920) a partir de un segmento:
    - Corte exacto con -ss y -to.
    - Recorte vertical 9:16 (centro por defecto, o posición manual).
    - Subtítulos quemados estilo reels (ASS con palabra resaltada).
    - Normalización de audio con filtro loudnorm (-16 LUFS).
    """
    video_path = Path(video_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clip_dir = output_path.parent
    offset_val = get_crop_offset(crop_mode, x_offset)

    # Preparar archivo ASS de subtítulos si se requiere quemar
    ass_relative_name: Optional[str] = None
    temp_ass_path: Optional[Path] = None

    if burn_subtitles:
        if subtitles_ass_path and Path(subtitles_ass_path).exists():
            source_ass = Path(subtitles_ass_path).resolve()
            temp_ass_path = clip_dir / f"temp_{highlight.id:02d}.ass"
            shutil.copyfile(source_ass, temp_ass_path)
            ass_relative_name = temp_ass_path.name
        elif transcript is not None:
            # Generar los subtítulos dinámicos ASS desde el transcript
            temp_ass_path = clip_dir / f"temp_{highlight.id:02d}.ass"
            clip_words = extract_words_for_clip(transcript, highlight.start, highlight.end)
            generate_ass_subtitles(
                words=clip_words,
                clip_start=highlight.start,
                clip_end=highlight.end,
                output_path=temp_ass_path,
            )
            ass_relative_name = temp_ass_path.name

    # Construir cadena de filtros de video
    # 1. Recorte 9:16: crop=ih*9/16:ih:(iw-ow)*offset:0
    # 2. Escala a resolución final estándar: scale=1080:1920
    # 3. Relación de aspecto de píxeles: setsar=1
    video_filters = [
        f"crop=ih*(9/16):ih:(iw-ow)*{offset_val:.4f}:0",
        "scale=1080:1920",
        "setsar=1",
    ]

    if ass_relative_name:
        video_filters.append(f"ass={ass_relative_name}")

    vf_chain = ",".join(video_filters)
    # Filtro de audio para normalización estándar EBU R128 (-16 LUFS para redes sociales)
    af_chain = "loudnorm=I=-16:TP=-1.5:LRA=11"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{highlight.start:.3f}",
        "-to",
        f"{highlight.end:.3f}",
        "-i",
        str(video_path),
        "-vf",
        vf_chain,
        "-af",
        af_chain,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path.name),
    ]

    logger.info(
        f"Renderizando clip #{highlight.id} [{highlight.start:.1f}s - {highlight.end:.1f}s] -> {output_path.name}"
    )

    # Ejecutar en el directorio de salida para garantizar que libass cargue el archivo ASS sin fallos de ruta en Windows
    result = subprocess.run(cmd, cwd=str(clip_dir), capture_output=True, text=True)

    # Limpiar archivo temporal ASS
    if temp_ass_path and temp_ass_path.exists():
        try:
            temp_ass_path.unlink()
        except Exception:
            pass

    if result.returncode != 0:
        logger.error(f"Error renderizando clip con ffmpeg: {result.stderr}")
        raise RuntimeError(f"Fallo en renderizado del clip #{highlight.id}: {result.stderr}")

    return output_path


def render_all_highlights(
    video_path: Path,
    highlights: List[HighlightSegment],
    output_dir: Path,
    transcript: Optional[Transcript] = None,
    crop_mode: str = "center",
    x_offset: Optional[float] = None,
    burn_subtitles: bool = True,
) -> List[Path]:
    """
    Renderiza todos los momentos destacados de la lista en la carpeta de salida (por defecto clips/).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_clips: List[Path] = []
    for h in highlights:
        title_slug = slugify(h.title, max_words=4)
        clip_name = f"clip_{h.id:02d}_{title_slug}.mp4"
        clip_path = output_dir / clip_name

        rendered = render_clip(
            video_path=video_path,
            highlight=h,
            output_path=clip_path,
            transcript=transcript,
            crop_mode=crop_mode,
            x_offset=x_offset,
            burn_subtitles=burn_subtitles,
        )
        generated_clips.append(rendered)

    return generated_clips
