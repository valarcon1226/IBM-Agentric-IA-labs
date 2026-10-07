# 23-A · Kit de reutilización de video: clips verticales, subtítulos y paquete de YouTube

Carpeta nueva: `Portfolio-Automation/23-video-repurposing-kit` (solo esta). Para los gigs de clipping ("edit instagram
reels", "edit short videos") y de agencia de YouTube del Trend Spotter. Objetivo: que una persona entregue 10 clips de un
podcast en 30 minutos en vez de 4 horas. Todo local y gratis.

1. Entrada: un archivo de video (mp4/mov). Opcional: URL de YouTube con `yt-dlp`, con un aviso en el README de que
   solo se usa con videos propios, con permiso o con licencia Creative Commons.
2. Transcripción local con `faster-whisper` (modelo `small` en CPU por defecto, configurable) con marcas de tiempo por
   palabra. Guarda `transcript.json` y `.srt`.
3. Selección de momentos: el LLM local (Ollama, endpoint compatible con OpenAI en `.env`) recibe la transcripción por
   bloques y devuelve JSON validado con pydantic: 5–10 segmentos de 20–60 s con gancho, título y puntaje. Si no hay LLM,
   un modo heurístico simple (frases completas, sin cortar palabras). La persona puede editar `highlights.json` y
   volver a renderizar solo ese paso.
4. Render con `ffmpeg`: corte exacto, recorte vertical 9:16 (centro por defecto; opción de posición manual), subtítulos
   quemados estilo reels (ASS, palabra resaltada, tamaño legible en celular), normalización de audio. Salida `clips/`.
5. Paquete de YouTube desde la transcripción: capítulos con tiempos, 3 títulos, descripción con capítulos y 10 tags
   (`youtube_package.md`).
6. CLI (`python -m kit run video.mp4`) y una interfaz web mínima (Gradio o FastAPI + HTML) para subir, revisar los
   momentos, cambiarlos y descargar.
7. Tests: genera un video de prueba de 2 min con `ffmpeg` (testsrc + audio de voz sintética o un audio CC0 que
   anotes) y prueba cada paso con el LLM falso; el render se verifica con `ffprobe` (duración, 1080x1920, pista de
   subtítulos quemada = frames distintos). `README.md` en español para vender el servicio + `docs/DEMO-SCRIPT.md`.

Verificación (salida real): `pytest -q`, una corrida completa del CLI sobre el video de prueba con la lista de archivos
generados y su `ffprobe`. No subas videos pesados al repo (agrega `.gitignore`).

Reglas: ponytail, sin commit ni push, sin secretos, no toques otras carpetas. La laptop tiene poca memoria: nada de
modelos grandes. Al terminar escribe `docs/reviews/T-23-A.md` (español) con la salida real de cada comando.
