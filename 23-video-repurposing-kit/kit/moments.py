"""Módulo de selección de momentos virales (LLM local u heurística) con validación Pydantic."""

import json
import logging
import os
from pathlib import Path
import re
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field, model_validator

from kit.transcriber import Transcript

logger = logging.getLogger(__name__)


class HighlightSegment(BaseModel):
    """Segmento de video seleccionado para clip vertical."""
    id: int
    start: float = Field(ge=0.0, description="Segundo de inicio del clip")
    end: float = Field(gt=0.0, description="Segundo de fin del clip")
    duration: float = Field(default=0.0, description="Duración en segundos")
    title: str = Field(description="Título atractivo del clip")
    hook: str = Field(description="Frase gancho inicial para los primeros 3 segundos")
    score: float = Field(ge=0.0, le=100.0, description="Puntuación de impacto o viralidad")
    reason: Optional[str] = Field(default="", description="Explicación del momento")

    @model_validator(mode="after")
    def compute_and_check_duration(self) -> "HighlightSegment":
        if self.end <= self.start:
            raise ValueError(f"El fin ({self.end}) debe ser mayor que el inicio ({self.start})")
        computed = round(self.end - self.start, 3)
        if self.duration <= 0.0 or abs(self.duration - computed) > 0.5:
            self.duration = computed
        return self


class HighlightsCollection(BaseModel):
    """Colección de momentos destacados listos para renderizar."""
    video_file: str = Field(default="", description="Nombre o ruta del archivo de video")
    highlights: List[HighlightSegment] = Field(
        default_factory=list,
        description="Lista de 5 a 10 segmentos destacados",
    )


def select_moments_heuristic(
    transcript: Transcript,
    video_file: str = "",
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    target_count: int = 5,
) -> HighlightsCollection:
    """
    Selecciona momentos virales mediante análisis heurístico simple:
    - Agrupa frases completas sin cortar palabras.
    - Longitud de cada segmento entre 20 y 60 segundos.
    - Selecciona frases con interrogaciones, exclamaciones o palabras de enganche.
    """
    segments = transcript.segments
    if not segments:
        return HighlightsCollection(video_file=video_file, highlights=[])

    total_duration = transcript.duration or (segments[-1].end if segments else 0.0)
    candidates: List[HighlightSegment] = []

    # Identificar bloques continuos
    n = len(segments)
    highlight_id = 1

    # Palabras clave de gancho en español / inglés
    hook_keywords = {
        "secreto", "clave", "importante", "error", "nadie", "nunca", "siempre",
        "verdad", "como", "por que", "increible", "mejor", "peor", "truco",
        "consejo", "atencion", "mira", "aprende", "estrategia", "resultado",
        "secret", "mistake", "never", "always", "truth", "how", "why", "best"
    }

    # Búsqueda de ventanas temporales coherentes
    i = 0
    while i < n and len(candidates) < 10:
        win_start = segments[i].start
        win_text_parts: List[str] = []

        for j in range(i, n):
            cur_seg = segments[j]
            win_text_parts.append(cur_seg.text)
            curr_dur = cur_seg.end - win_start

            # Si alcanzamos la duración mínima deseada
            if curr_dur >= min_duration:
                # Comprobar si termina con puntuación final (. ! ?)
                ends_sentence = cur_seg.text.strip().endswith((".", "!", "?"))
                if ends_sentence or curr_dur >= max_duration - 5.0 or j == n - 1:
                    win_end = cur_seg.end
                    clip_text = " ".join(win_text_parts).strip()
                    first_sentence = re.split(r"[.!?]", clip_text)[0].strip()
                    hook = first_sentence if len(first_sentence) > 10 else clip_text[:60]

                    # Calcular puntaje heurístico
                    text_lower = clip_text.lower()
                    matches = sum(1 for kw in hook_keywords if kw in text_lower)
                    question_bonus = 1.0 if "?" in clip_text or "¿" in clip_text else 0.0
                    excl_bonus = 0.5 if "!" in clip_text or "¡" in clip_text else 0.0
                    score = min(10.0, round(7.0 + (matches * 0.5) + question_bonus + excl_bonus, 1))

                    # Generar título
                    words = clip_text.split()
                    title = " ".join(words[:6]).title()
                    if len(title) > 40:
                        title = title[:37] + "..."

                    candidates.append(
                        HighlightSegment(
                            id=highlight_id,
                            start=round(win_start, 2),
                            end=round(win_end, 2),
                            duration=round(win_end - win_start, 2),
                            title=f"Momento #{highlight_id}: {title}",
                            hook=hook,
                            score=score,
                            reason=f"Párrafo coherente de {round(win_end - win_start, 1)}s con gancho inicial.",
                        )
                    )
                    highlight_id += 1
                    break
        # Avanzar el inicio al siguiente segmento o salto prudente
        next_i = i + 1
        while next_i < n and (segments[next_i].start - win_start) < (min_duration * 0.6):
            next_i += 1
        i = next_i if next_i > i else i + 1

    # Si hay muy pocos candidatos pero el video dura al menos min_duration
    if not candidates and total_duration >= min_duration:
        end_time = min(total_duration, min_duration + 10.0)
        candidates.append(
            HighlightSegment(
                id=1,
                start=0.0,
                end=round(end_time, 2),
                duration=round(end_time, 2),
                title="Momento Clave del Video",
                hook=segments[0].text[:60] if segments else "Mira este momento",
                score=8.5,
                reason="Segmento inicial de alta retención.",
            )
        )

    return HighlightsCollection(video_file=video_file, highlights=candidates)


def select_moments_llm(
    transcript: Transcript,
    video_file: str = "",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> HighlightsCollection:
    """
    Selecciona momentos virales usando un LLM local compatible con OpenAI (Ollama u otro).
    Valida el resultado con Pydantic. Si falla o no está disponible, recurre a heurística.
    """
    base_url = base_url or os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")
    api_key = api_key or os.getenv("OPENAI_API_KEY", "ollama")
    model = model or os.getenv("LLM_MODEL", "llama3")

    # Formatear la transcripción con marcas de tiempo en bloques
    transcript_blocks: List[str] = []
    for s in transcript.segments:
        m_start = int(s.start // 60)
        sec_start = int(s.start % 60)
        m_end = int(s.end // 60)
        sec_end = int(s.end % 60)
        transcript_blocks.append(f"[{m_start:02d}:{sec_start:02d} - {m_end:02d}:{sec_end:02d}] {s.text}")

    formatted_transcript = "\n".join(transcript_blocks)

    system_prompt = (
        "Eres un editor profesional experto en YouTube Shorts, TikTok e Instagram Reels. "
        "Tu tarea es analizar la transcripción de un video y seleccionar entre 5 y 10 momentos "
        "de alto impacto, entre 20 y 60 segundos de duración cada uno. "
        "Debes devolver EXCLUSIVAMENTE un objeto JSON válido con la siguiente estructura:\n"
        "{\n"
        '  "video_file": "' + video_file + '",\n'
        '  "highlights": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "start": 12.5,\n'
        '      "end": 45.0,\n'
        '      "duration": 32.5,\n'
        '      "title": "Título corto y llamativo",\n'
        '      "hook": "La frase gancho inicial exacta",\n'
        '      "score": 9.5,\n'
        '      "reason": "Por qué este momento retiene a la audiencia"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Reglas estrictas:\n"
        "- Cada momento debe durar entre 20 y 60 segundos (end - start).\n"
        "- start y end deben ser números decimales en segundos.\n"
        "- El gancho (hook) debe capturar la atención en los primeros 3 segundos.\n"
        "- Devuelve SOLO el JSON sin texto introductorio ni explicaciones fuera del JSON."
    )

    user_prompt = f"Transcripción del video:\n{formatted_transcript}\n\nSelecciona los 5-10 mejores clips virales."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"} if "ollama" in base_url or "openai" in base_url else None,
    }

    try:
        logger.info(f"Consultando LLM en {endpoint} con modelo {model}...")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Limpiar posible markdown ```json ... ```
            clean_content = content.strip()
            if clean_content.startswith("```"):
                clean_content = re.sub(r"^```(?:json)?\s*", "", clean_content)
                clean_content = re.sub(r"\s*```$", "", clean_content)

            json_data = json.loads(clean_content)
            if "video_file" not in json_data or not json_data["video_file"]:
                json_data["video_file"] = video_file

            validated = HighlightsCollection.model_validate(json_data)
            if validated.highlights:
                return validated

            logger.warning("El LLM devolvió lista vacía de highlights, aplicando heurística...")
    except Exception as exc:
        logger.warning(f"No se pudo consultar el LLM ({exc}). Activando modo heurístico...")

    return select_moments_heuristic(transcript, video_file=video_file)


def save_highlights_json(collection: HighlightsCollection, output_path: Path) -> Path:
    """Guarda los highlights seleccionados en formato JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(collection.model_dump_json(indent=2))
    return output_path


def load_highlights_json(json_path: Path) -> HighlightsCollection:
    """Carga highlights.json existente para permitir edición manual y re-renderizado."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return HighlightsCollection.model_validate(data)
