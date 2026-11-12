"""Módulo de descarga de videos desde YouTube con yt-dlp."""

from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

YOUTUBE_NOTICE = (
    "AVISO LEGAL IMPORTANTE: La descarga de videos mediante yt-dlp solo debe realizarse "
    "con videos de tu propiedad, con autorización explícita del creador o bajo licencias "
    "abiertas como Creative Commons. Respeta siempre los términos del servicio y derechos de autor."
)

URL_PATTERN = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be)/.+$", re.IGNORECASE)


def is_youtube_url(url_or_path: str) -> bool:
    """Verifica si la cadena dada corresponde a una URL de YouTube."""
    if not isinstance(url_or_path, str):
        return False
    return bool(URL_PATTERN.match(url_or_path.strip()))


def download_youtube_video(url: str, output_dir: Path) -> Path:
    """
    Descarga un video de YouTube en formato MP4 (máximo 1080p) usando yt-dlp.

    Imprime el aviso legal y devuelve la ruta al archivo descargado.
    """
    print(f"\n[AVISO] {YOUTUBE_NOTICE}\n")
    logger.info(YOUTUBE_NOTICE)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import yt_dlp

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(output_dir / "%(id)s_%(title).40s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        downloaded_path = Path(filename)
        # Si yt-dlp cambió la extensión a mp4 tras el merge
        if not downloaded_path.exists():
            mp4_path = downloaded_path.with_suffix(".mp4")
            if mp4_path.exists():
                return mp4_path
        return downloaded_path
