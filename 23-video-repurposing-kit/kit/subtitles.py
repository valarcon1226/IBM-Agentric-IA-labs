"""Módulo de generación de subtítulos ASS dinámicos con palabra resaltada estilo Reels/TikTok."""

from pathlib import Path
from typing import List

from kit.transcriber import Transcript, WordTiming


def format_ass_time(seconds: float) -> str:
    """Convierte segundos a formato de tiempo ASS (H:MM:SS.cc)."""
    if seconds < 0:
        seconds = 0.0
    total_centis = int(round(seconds * 100))
    hours = total_centis // 360000
    rem = total_centis % 360000
    minutes = rem // 6000
    rem = rem % 6000
    secs = rem // 100
    centis = rem % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def generate_ass_subtitles(
    words: List[WordTiming],
    clip_start: float,
    clip_end: float,
    output_path: Path,
    words_per_line: int = 4,
    font_name: str = "Arial",
    font_size: int = 64,
    highlight_color: str = "&H0000FFFF&",  # Amarillo en formato ASS (&HAABBGGRR&)
    primary_color: str = "&H00FFFFFF&",    # Blanco opaco
    outline_color: str = "&H00000000&",    # Borde negro
    outline_width: int = 4,
    shadow_width: int = 2,
    margin_v: int = 420,  # Ubicación óptima (sobre controles de UI móviles)
) -> Path:
    """
    Genera un archivo de subtítulos ASS para un clip vertical de 1080x1920 con:
    - Tipografía grande y legible en pantallas de móvil.
    - Contorno grueso y sombra para contraste sobre cualquier fondo.
    - Frases cortas de 3 a 5 palabras.
    - Efecto dinámico de palabra resaltada al pronunciarse (estilo Reels/Shorts).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ReelsDefault,{font_name},{font_size},{primary_color},{highlight_color},{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},{shadow_width},2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines: List[str] = []

    # Filtrar palabras que pertenezcan al rango del clip
    clip_words = [
        w for w in words
        if w.end > clip_start and w.start < clip_end
    ]

    if not clip_words:
        # Si no hay marcas por palabra en ese rango, creamos un archivo ASS vacío
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
        return output_path

    # Agrupar palabras en frases cortas de `words_per_line` (estilo Reels)
    chunks: List[List[WordTiming]] = []
    current_chunk: List[WordTiming] = []

    for w in clip_words:
        current_chunk.append(w)
        # Cortar chunk si llega a words_per_line o si la palabra termina con punto/interrogación
        if len(current_chunk) >= words_per_line or w.word.strip().endswith((".", "!", "?", "...", ":")):
            chunks.append(current_chunk)
            current_chunk = []
    if current_chunk:
        chunks.append(current_chunk)

    # Generar eventos de diálogo con palabra resaltada
    for chunk in chunks:
        chunk_words_text = [cw.word.strip().upper() for cw in chunk]

        for idx, active_word in enumerate(chunk):
            w_start_rel = max(0.0, active_word.start - clip_start)
            w_end_rel = max(w_start_rel + 0.1, active_word.end - clip_start)

            # Si el siguiente inicia un poco después, extender hasta el siguiente
            if idx + 1 < len(chunk):
                next_start_rel = max(0.0, chunk[idx + 1].start - clip_start)
                if next_start_rel > w_start_rel:
                    w_end_rel = next_start_rel

            start_ass = format_ass_time(w_start_rel)
            end_ass = format_ass_time(w_end_rel)

            # Construir texto donde la palabra activa tiene el color destacado
            formatted_words = []
            for j, wtext in enumerate(chunk_words_text):
                if j == idx:
                    formatted_words.append(f"{{\\c{highlight_color}\\b1}}{wtext}{{\\c{primary_color}\\b1}}")
                else:
                    formatted_words.append(wtext)

            line_text = " ".join(formatted_words)
            dialogue_lines.append(f"Dialogue: 0,{start_ass},{end_ass},ReelsDefault,,0,0,0,,{line_text}")

    full_content = header + "\n".join(dialogue_lines) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    return output_path


def extract_words_for_clip(transcript: Transcript, start: float, end: float) -> List[WordTiming]:
    """Extrae la lista ordenada de palabras correspondientes a un intervalo de tiempo."""
    all_words: List[WordTiming] = []
    for s in transcript.segments:
        if s.end > start and s.start < end:
            if s.words:
                all_words.extend(s.words)
            else:
                # Si el segmento no tiene palabras individuales, repartir el tiempo equitativamente
                raw_words = s.text.split()
                if raw_words:
                    word_duration = (s.end - s.start) / len(raw_words)
                    cur_t = s.start
                    for rw in raw_words:
                        all_words.append(
                            WordTiming(
                                word=rw,
                                start=round(cur_t, 3),
                                end=round(cur_t + word_duration, 3),
                                probability=1.0,
                            )
                        )
                        cur_t += word_duration

    # Ordenar por tiempo
    all_words.sort(key=lambda w: w.start)
    return [w for w in all_words if w.end > start and w.start < end]
