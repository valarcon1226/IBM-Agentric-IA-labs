"""Módulo para generar el paquete completo de YouTube a partir de la transcripción."""

from pathlib import Path
import re
from typing import List, Optional

from kit.moments import HighlightSegment
from kit.transcriber import Transcript


def format_youtube_time(seconds: float) -> str:
    """Convierte segundos a formato de timestamp para YouTube (MM:SS o HH:MM:SS)."""
    if seconds < 0:
        seconds = 0.0
    total_secs = int(seconds)
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def generate_youtube_package(
    transcript: Transcript,
    highlights: Optional[List[HighlightSegment]] = None,
    output_path: Optional[Path] = None,
    video_topic: Optional[str] = None,
) -> str:
    """
    Genera el archivo youtube_package.md con:
    - 3 títulos atractivos de alto CTR.
    - Capítulos con marcas de tiempo (iniciando en 00:00 como exige YouTube).
    - Descripción optimizada con capítulos y llamada a la acción.
    - 10 tags SEO listos para copiar y pegar en YouTube Studio.
    """
    highlights = highlights or []
    topic = video_topic or "Claves de Negocio y Crecimiento"

    # 1. Capítulos de YouTube
    chapters: List[str] = ["00:00 Introducción y bienvenida"]

    # Usar los momentos destacados o intervalos de tiempo para los capítulos
    if highlights:
        for h in highlights:
            # YouTube requiere al menos 10 segundos entre capítulos
            if h.start >= 10.0:
                ts_str = format_youtube_time(h.start)
                clean_title = re.sub(r"^Momento #\d+:\s*", "", h.title).strip()
                chapters.append(f"{ts_str} {clean_title}")
    else:
        # Generar capítulos distribuidos uniformemente desde los segmentos
        duration = transcript.duration or 120.0
        step = max(30.0, duration / 4.0)
        curr = step
        c_idx = 1
        while curr < duration - 10.0:
            ts_str = format_youtube_time(curr)
            chapters.append(f"{ts_str} Punto clave #{c_idx}")
            curr += step
            c_idx += 1

    chapters_block = "\n".join(chapters)

    # 2. 3 Títulos de alto CTR
    title_1 = f"Cómo Dominar {topic} en 2026 (Paso a Paso)"
    title_2 = f"El Secreto de {topic} que Nadie te Está Contando"
    title_3 = f"Hice Esto en {topic} y los Resultados Fueron Increíbles"

    # 3. Tags SEO (10 tags optimizados)
    tags_list = [
        f"{topic.lower()}",
        "estrategia de contenido",
        "crecimiento digital",
        "tutorial 2026",
        "productividad",
        "automatizacion",
        "podcast clips",
        "reutilizacion de video",
        "consejos de expertos",
        "como empezar",
    ]
    tags_bullets = "\n".join(f"- `{t}`" for t in tags_list)
    tags_csv = ", ".join(tags_list)

    # 4. Descripción completa
    summary_text = transcript.full_text[:350].strip()
    if summary_text:
        summary_text += "..."
    else:
        summary_text = f"En este episodio exploramos a fondo todo lo necesario sobre {topic}."

    description_body = f"""{summary_text}

👇 CAPÍTULOS DEL VIDEO:
{chapters_block}

🔔 Suscríbete para no perderte ningún video sobre automatización y crecimiento.
💬 Déjame en los comentarios tu opinión o preguntas sobre este episodio.

📌 Recursos y enlaces:
- Sitio Web: https://example.com
- Contacto: contacto@example.com

#Crecimiento #{topic.replace(' ', '')} #Automatizacion #Podcast"""

    markdown_content = f"""# Paquete de YouTube: {topic}

## 🎯 3 Opciones de Títulos (Alto CTR)
1. **Opción Directa / Beneficio:** `{title_1}`
2. **Opción Curiosidad / Revelación:** `{title_2}`
3. **Opción Historia / Impacto:** `{title_3}`

---

## ⏱️ Capítulos con Tiempos (Formato YouTube)
```text
{chapters_block}
```

---

## 📝 Descripción Completa para YouTube
```markdown
{description_body}
```

---

## 🏷️ 10 Tags SEO Recomendados
{tags_bullets}

### Copiar y pegar en YouTube Studio:
```text
{tags_csv}
```
"""

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

    return markdown_content
