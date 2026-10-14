# 🎬 Kit de Reutilización de Video: Clips Verticales, Subtítulos y Paquete de YouTube

> **Multiplica el impacto de tu contenido largo en minutos.**  
> Transforma un video horizontal o podcast de 1 hora en **10 clips verticales virales (9:16) con subtítulos dinámicos estilo TikTok** y un **paquete completo de publicación para YouTube**, todo ejecutado **100% en tu máquina local y sin costos de APIs externas**.

---

## ⚡ El Problema vs. La Solución

| Flujo Tradicional (Manual) | Con Video Repurposing Kit |
|---|---|
| **4 horas** buscando momentos a mano en la línea de tiempo. | **5 minutos** de análisis inteligente (LLM local o heurística). |
| Recorte manual y reencuadre cuadro a cuadro. | Recorte vertical **9:16 automático (1080x1920)** con opción de ajuste. |
| Subtitulado manual palabra por palabra. | **Subtítulos ASS quemados con palabra resaltada** en amarillo. |
| Niveles de volumen desiguales entre clips. | **Normalización de audio broadcast** (EBU R128 loudnorm a -16 LUFS). |
| Redacción manual de títulos, capítulos y tags. | Generación automática de `youtube_package.md` listo para publicar. |
| **Costo:** $15–$50 USD en suscripciones mensuales de SaaS. | **$0 USD (100% local, privado y gratis).** |

---

## 🚀 Servicios Ofrecidos / Paquetes Comerciales

Diseñado para gigs de alta demanda en plataformas como Upwork, Fiverr y agencias de creadores:
* *"Edit Instagram Reels & TikTok shorts from long form podcasts"*
* *"YouTube content repurposing & YouTube SEO packaging"*
* *"Trend Spotting & Viral Clipping Agency"*

### Paquetes para Clientes:
1. **Paquete Starter (5 Clips):** 5 reels verticales de 20–60s + subtítulos dinámicos + audio masterizado.
2. **Paquete Pro Podcaster (10 Clips + YouTube Pack):** 10 reels verticales + archivo `youtube_package.md` con capítulos de YouTube, 3 opciones de títulos virales de alto CTR, descripción completa y 10 tags SEO.
3. **Paquete Agencia Mensual:** 4 episodios al mes (40 clips + 4 paquetes de YouTube completos) entregados en menos de 24 horas.

---

## ⚖️ Aviso Legal de Uso Responsable (YouTube / yt-dlp)

> **IMPORTANTE:** La funcionalidad opcional de descarga mediante URL (`yt-dlp`) debe utilizarse **únicamente** con videos de tu propia autoría, videos con autorización explícita y por escrito de los titulares de derechos, o material publicado bajo licencias abiertas compatibles (como Creative Commons CC-BY). Respeta siempre la legislación vigente de derechos de autor y los términos de servicio de las plataformas.

---

## 🛠️ Arquitectura y Funcionamiento

El kit se compone de 5 etapas modulares totalmente locales:

```
[ Video MP4/MOV o URL ]
          │
          ▼
   1. Extracción de Audio ──► faster-whisper (small en CPU, int8) ──► transcript.json & .srt
          │
          ▼
   2. Detección de Momentos (Ollama LLM local / Heurística) ──► highlights.json (Editable)
          │
          ▼
   3. Renderizado ffmpeg ──► 1080x1920 (9:16) + ASS Subtítulos Resaltados + Audio Loudnorm
          │
          ├──► clips/clip_01_*.mp4 ... clip_10_*.mp4
          │
          ▼
   4. Paquete de YouTube ──► youtube_package.md (Capítulos, 3 Títulos, Descripción, 10 Tags)
```

1. **Entrada flexible:** Admite archivos `.mp4` y `.mov` locales o descarga con `yt-dlp`.
2. **Transcripción local (`faster-whisper`):** Modelo `small` por defecto cuantizado en `int8` para funcionar fluido en laptops con CPU estándar y poca memoria RAM. Genera marcas de tiempo por palabra.
3. **Selección de momentos virales:**
   - **Modo LLM local:** Conexión con Ollama u endpoint OpenAI compatible (`.env`). Devuelve JSON validado con **Pydantic** con 5–10 momentos de 20–60 segundos con gancho inicial (`hook`), título y score de retención.
   - **Modo Heurístico:** Fallback automático sin cortes de palabras ni frases truncadas si no hay un LLM en ejecución.
   - **Edición humana:** El archivo `highlights.json` puede ser editado directamente y re-renderizado en segundos.
4. **Renderizado con `ffmpeg`:**
   - Corte exacto con `-ss` y `-to`.
   - Encuadre vertical 9:16 (1080x1920) centrado o con ajuste manual (`--crop left|center|right` o `--x-offset 0.0-1.0`).
   - Subtítulos quemados estilo Reels con tipografía legible en pantallas móviles y resaltado dinámico de la palabra que se pronuncia en tiempo real.
   - Normalización de audio broadcast con filtro `loudnorm` (-16 LUFS).
5. **Paquete de YouTube (`youtube_package.md`):**
   - 3 títulos magnéticos de alto CTR (Directo, Curiosidad, Historia).
   - Capítulos con timestamps iniciando obligatoriamente en `00:00`.
   - Descripción completa formateada con llamadas a la acción (CTA).
   - 10 tags SEO listos para copiar y pegar en YouTube Studio.
6. **CLI y Panel Web (FastAPI):**
   - CLI completa con subcomandos `run`, `render`, `youtube` y `serve`.
   - Panel web responsive para previsualizar los momentos, editarlos en una tabla interactiva y descargar los clips directamente.

---

## 💻 Instalación y Requisitos

### Requisitos del Sistema:
- Python 3.11 o 3.12
- `ffmpeg` y `ffprobe` instalados en el PATH del sistema
- (Opcional) `Ollama` corriendo localmente con modelo `llama3` para el análisis por LLM

### Instalación:
```bash
# Clonar o ubicarse en la carpeta
cd 23-video-repurposing-kit

# Crear y activar entorno virtual
uv venv -p 3.12 .venv
.venv\Scripts\activate

# Instalar dependencias
uv pip install -r requirements-dev.txt
```

### Configuración (`.env`):
Copia `.env.example` a `.env`:
```ini
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_API_KEY=ollama
LLM_MODEL=llama3
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

---

## 📖 Guía de Uso

### 1. Ejecutar el Pipeline Completo (CLI)
```bash
python -m kit run ruta/a/tu_video.mp4
```
O con una URL de YouTube autorizada:
```bash
python -m kit run "https://www.youtube.com/watch?v=..."
```

Opciones principales:
* `--output-dir / -o`: Carpeta de salida (por defecto `output/`).
* `--no-llm`: Forzar modo heurístico rápido sin LLM.
* `--model`: Cambiar modelo de whisper (`tiny`, `base`, `small`, `medium`).
* `--crop`: Recorte vertical (`center`, `left`, `right`).
* `--no-subtitles`: Generar clips sin subtítulos quemados.

### 2. Re-renderizar Momentos Editados
Si abres `output/highlights.json`, ajustas los tiempos o títulos y quieres generar los clips nuevamente:
```bash
python -m kit render ruta/a/tu_video.mp4 output/highlights.json --transcript output/transcript.json
```

### 3. Iniciar el Panel de Control Web
```bash
python -m kit serve --port 8000
```
Abre tu navegador en `http://localhost:8000` para subir videos, revisar los momentos en una tabla editable, disparar el renderizado y previsualizar los videos finales.

---

## 🧪 Pruebas Automatizadas

El proyecto incluye una suite de pruebas con `pytest` que verifica:
* Extracción y transcripción con marcas por palabra.
* Selección de momentos con LLM falso y validación con Pydantic.
* Generación de subtítulos ASS y resaltado de palabras.
* Verificación con `ffprobe` de duración, resolución 1080x1920 y quemado físico de subtítulos.
* Endpoints de la interfaz web y ejecución completa del CLI.

Para correr los tests:
```bash
.venv\Scripts\python.exe -m pytest -q
```
