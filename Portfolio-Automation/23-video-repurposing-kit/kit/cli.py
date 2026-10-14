"""Línea de comandos (CLI) para el kit de reutilización de video."""

import argparse
import logging
from pathlib import Path
import sys
from typing import List, Optional

from kit.downloader import download_youtube_video, is_youtube_url
from kit.moments import (
    load_highlights_json,
    save_highlights_json,
    select_moments_heuristic,
    select_moments_llm,
)
from kit.renderer import render_all_highlights
from kit.transcriber import (
    extract_audio,
    load_transcript_json,
    save_transcript_json,
    save_transcript_srt,
    transcribe_audio,
)
from kit.youtube import generate_youtube_package

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("kit")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_pipeline(
    video_or_url: str,
    output_dir: Path = Path("output"),
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    use_llm: bool = True,
    crop_mode: str = "center",
    x_offset: Optional[float] = None,
    burn_subtitles: bool = True,
) -> dict:
    """Ejecuta el flujo completo de reutilización de video de extremo a extremo."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("=== VIDEO REPURPOSING KIT — INICIANDO PROCESO ===")
    print("=" * 60)

    # 1. Entrada y descarga
    if is_youtube_url(video_or_url):
        print("\n[1/5] Descargando video desde YouTube...")
        video_path = download_youtube_video(video_or_url, output_dir / "downloads")
    else:
        video_path = Path(video_or_url).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"El video especificado no existe: {video_path}")
        print(f"\n[1/5] Video de entrada: {video_path.name}")

    # 2. Extracción de audio y transcripción
    print(f"\n[2/5] Extrayendo audio y transcribiendo con faster-whisper ({model_size})...")
    audio_path = output_dir / "audio.wav"
    extract_audio(video_path, audio_path)

    transcript = transcribe_audio(
        audio_path,
        model_size=model_size,
        device=device,
        compute_type=compute_type,
    )
    transcript_json = output_dir / "transcript.json"
    transcript_srt = output_dir / "transcript.srt"
    save_transcript_json(transcript, transcript_json)
    save_transcript_srt(transcript, transcript_srt)
    print(f"  [OK] Transcripción guardada: {transcript_json.name}")
    print(f"  [OK] Subtítulos SRT guardados: {transcript_srt.name}")
    print(f"  [OK] Duración total detectada: {transcript.duration:.1f}s ({len(transcript.segments)} segmentos)")

    # 3. Selección de momentos virales
    print("\n[3/5] Seleccionando momentos destacados (20-60s)...")
    if use_llm:
        highlights_coll = select_moments_llm(
            transcript,
            video_file=video_path.name,
        )
    else:
        highlights_coll = select_moments_heuristic(
            transcript,
            video_file=video_path.name,
        )

    highlights_json = output_dir / "highlights.json"
    save_highlights_json(highlights_coll, highlights_json)
    print(f"  [OK] Se seleccionaron {len(highlights_coll.highlights)} momentos virales.")
    print(f"  [OK] Momentos guardados en {highlights_json.name} (puedes editarlos y re-renderizar).")
    for h in highlights_coll.highlights:
        print(f"     * [{h.start:.1f}s - {h.end:.1f}s | {h.duration:.1f}s] {h.title} (Score: {h.score})")

    # 4. Renderizado con ffmpeg
    print("\n[4/5] Renderizando clips verticales 9:16 (1080x1920) con subtítulos estilo Reels...")
    clips_dir = output_dir / "clips"
    rendered_clips = render_all_highlights(
        video_path=video_path,
        highlights=highlights_coll.highlights,
        output_dir=clips_dir,
        transcript=transcript,
        crop_mode=crop_mode,
        x_offset=x_offset,
        burn_subtitles=burn_subtitles,
    )
    print(f"  [OK] Se generaron con éxito {len(rendered_clips)} clips verticales en {clips_dir.name}/:")
    for clip in rendered_clips:
        print(f"     - {clip.name}")

    # 5. Paquete de YouTube
    print("\n[5/5] Generando paquete completo para YouTube (capítulos, títulos, descripción, tags)...")
    youtube_pkg_path = output_dir / "youtube_package.md"
    generate_youtube_package(
        transcript=transcript,
        highlights=highlights_coll.highlights,
        output_path=youtube_pkg_path,
        video_topic=video_path.stem.replace("_", " ").title(),
    )
    print(f"  [OK] Paquete de YouTube guardado en: {youtube_pkg_path.name}")

    print("\n" + "=" * 60)
    print("=== PROCESO COMPLETADO EXITOSAMENTE ===")
    print(f"Directorio de entrega: {output_dir.resolve()}")
    print("=" * 60 + "\n")

    return {
        "video_path": str(video_path),
        "transcript_json": str(transcript_json),
        "transcript_srt": str(transcript_srt),
        "highlights_json": str(highlights_json),
        "clips": [str(c) for c in rendered_clips],
        "youtube_package": str(youtube_pkg_path),
    }


def main(args: Optional[List[str]] = None) -> int:
    """Función de entrada CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m kit",
        description="Kit de reutilización de video: clips verticales, subtítulos y paquete de YouTube",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Subcomando run (por defecto o explícito)
    run_parser = subparsers.add_parser("run", help="Ejecutar el pipeline completo sobre un video o URL")
    run_parser.add_argument("video", help="Ruta al video local (mp4/mov) o URL de YouTube")
    run_parser.add_argument("--output-dir", "-o", default="output", help="Directorio de salida (default: output)")
    run_parser.add_argument("--model", "-m", default="small", help="Modelo de whisper (tiny, base, small, etc.)")
    run_parser.add_argument("--device", default="cpu", help="Dispositivo para whisper (cpu o cuda)")
    run_parser.add_argument("--compute-type", default="int8", help="Tipo de cómputo (int8, float32, etc.)")
    run_parser.add_argument("--no-llm", action="store_true", help="Usar solo heurística rápida sin llamar a un LLM")
    run_parser.add_argument("--crop", choices=["center", "left", "right"], default="center", help="Posición de recorte 9:16")
    run_parser.add_argument("--x-offset", type=float, default=None, help="Desplazamiento horizontal manual (0.0 a 1.0)")
    run_parser.add_argument("--no-subtitles", action="store_true", help="No quemar subtítulos en los videos")

    # Subcomando render (re-renderizar momentos existentes)
    render_parser = subparsers.add_parser("render", help="Renderizar clips a partir de highlights.json editado")
    render_parser.add_argument("video", help="Ruta al archivo de video original")
    render_parser.add_argument("highlights", help="Ruta al archivo highlights.json")
    render_parser.add_argument("--transcript", "-t", default=None, help="Ruta opcional a transcript.json para subtítulos")
    render_parser.add_argument("--output-dir", "-o", default="output/clips", help="Directorio para los clips")
    render_parser.add_argument("--crop", choices=["center", "left", "right"], default="center")
    render_parser.add_argument("--x-offset", type=float, default=None)

    # Subcomando youtube (generar paquete de youtube)
    yt_parser = subparsers.add_parser("youtube", help="Generar paquete de YouTube desde un transcript.json")
    yt_parser.add_argument("transcript", help="Ruta a transcript.json")
    yt_parser.add_argument("--highlights", default=None, help="Ruta opcional a highlights.json")
    yt_parser.add_argument("--output", "-o", default="youtube_package.md", help="Archivo de salida")

    # Subcomando serve (interfaz web)
    serve_parser = subparsers.add_parser("serve", help="Iniciar la interfaz web")
    serve_parser.add_argument("--port", "-p", type=int, default=8000, help="Puerto del servidor (default: 8000)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host del servidor (default: 127.0.0.1)")

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    if not parsed.command:
        # Si se pasa un archivo de video directamente sin subcomando (ej: python -m kit video.mp4)
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            # Tratar como 'run'
            return main(["run"] + sys.argv[1:])
        parser.print_help()
        return 0

    if parsed.command == "run":
        run_pipeline(
            video_or_url=parsed.video,
            output_dir=Path(parsed.output_dir),
            model_size=parsed.model,
            device=parsed.device,
            compute_type=parsed.compute_type,
            use_llm=not parsed.no_llm,
            crop_mode=parsed.crop,
            x_offset=parsed.x_offset,
            burn_subtitles=not parsed.no_subtitles,
        )
        return 0

    elif parsed.command == "render":
        h_coll = load_highlights_json(Path(parsed.highlights))
        transcript = load_transcript_json(Path(parsed.transcript)) if parsed.transcript else None
        render_all_highlights(
            video_path=Path(parsed.video),
            highlights=h_coll.highlights,
            output_dir=Path(parsed.output_dir),
            transcript=transcript,
            crop_mode=parsed.crop,
            x_offset=parsed.x_offset,
        )
        print(f"✓ Clips renderizados en {parsed.output_dir}")
        return 0

    elif parsed.command == "youtube":
        transcript = load_transcript_json(Path(parsed.transcript))
        highlights = load_highlights_json(Path(parsed.highlights)).highlights if parsed.highlights else None
        generate_youtube_package(
            transcript=transcript,
            highlights=highlights,
            output_path=Path(parsed.output),
        )
        print(f"[OK] Paquete de YouTube generado en {parsed.output}")
        return 0

    elif parsed.command == "serve":
        import uvicorn
        from kit.web import app
        print(f"\n[SERVIDOR] Servidor web iniciado en http://{parsed.host}:{parsed.port}\n")
        uvicorn.run(app, host=parsed.host, port=parsed.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
