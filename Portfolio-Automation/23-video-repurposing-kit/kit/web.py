"""Interfaz web mínima (FastAPI + HTML) para el kit de reutilización de video."""

import logging
from pathlib import Path
import shutil
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from kit.downloader import download_youtube_video, is_youtube_url, YOUTUBE_NOTICE
from kit.moments import (
    HighlightSegment,
    save_highlights_json,
    select_moments_heuristic,
    select_moments_llm,
)
from kit.renderer import render_all_highlights
from kit.transcriber import (
    extract_audio,
    save_transcript_json,
    save_transcript_srt,
    transcribe_audio,
)
from kit.youtube import generate_youtube_package

logger = logging.getLogger("kit.web")

app = FastAPI(title="Video Repurposing Kit", version="0.1.0")

# Directorios de trabajo
WORKSPACE_DIR = Path("web_workspace")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = WORKSPACE_DIR / "uploads"
CLIPS_DIR = WORKSPACE_DIR / "clips"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# Estado en memoria de la sesión
state = {
    "video_path": None,
    "transcript": None,
    "highlights": [],
    "rendered_clips": [],
    "youtube_package": None,
    "status": "Listo para cargar video",
}


class UpdateHighlightsRequest(BaseModel):
    highlights: List[HighlightSegment]


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Video Repurposing Kit — Panel de Control</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen p-4 md:p-8 font-sans">
  <div class="max-w-5xl mx-auto space-y-8">
    
    <!-- Encabezado -->
    <header class="border-b border-slate-700 pb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-indigo-400">🎬 Video Repurposing Kit</h1>
        <p class="text-sm text-slate-400">Convierte videos largos en 10 clips verticales 9:16 con subtítulos dinámicos y paquete de YouTube.</p>
      </div>
      <span class="bg-indigo-900/60 text-indigo-300 text-xs px-3 py-1.5 rounded-full border border-indigo-700">
        100% Local & Gratis
      </span>
    </header>

    <!-- Aviso Legal YouTube -->
    <div class="bg-amber-950/40 border border-amber-600/50 rounded-xl p-4 text-xs text-amber-200">
      <strong class="font-bold text-amber-400">⚖️ Aviso de Uso Responsable:</strong>
      __YOUTUBE_NOTICE__
    </div>

    <!-- Sección 1: Carga de Video -->
    <section class="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-xl space-y-4">
      <h2 class="text-lg font-bold text-slate-200 flex items-center gap-2">
        <span>1.</span> Selecciona tu video de entrada
      </h2>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Subir archivo -->
        <div class="border-2 border-dashed border-slate-600 rounded-xl p-6 text-center hover:border-indigo-500 transition">
          <input type="file" id="videoFile" accept="video/mp4,video/quicktime,video/*" class="hidden" onchange="handleFileSelected(event)">
          <label for="videoFile" class="cursor-pointer block">
            <svg class="mx-auto h-12 w-12 text-slate-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <span id="fileLabel" class="text-sm font-medium text-indigo-400">Haz clic para subir un video MP4 / MOV</span>
            <span class="block text-xs text-slate-500 mt-1">Videos de podcast, charlas o tutoriales</span>
          </label>
        </div>

        <!-- URL YouTube -->
        <div class="flex flex-col justify-between space-y-3 bg-slate-850 p-4 rounded-xl border border-slate-700">
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase mb-1">O descarga desde YouTube URL (Videos autorizados/CC):</label>
            <input type="url" id="youtubeUrl" placeholder="https://www.youtube.com/watch?v=..." class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500">
          </div>
          <button onclick="submitVideo()" id="processBtn" class="w-full bg-indigo-600 hover:bg-indigo-500 font-bold py-2.5 px-4 rounded-lg text-sm text-white transition shadow-lg">
            Procesar Transcripción y Momentos
          </button>
        </div>
      </div>

      <!-- Barra de estado -->
      <div id="statusAlert" class="hidden bg-slate-700/50 border border-slate-600 rounded-lg p-3 text-xs flex items-center justify-between">
        <span id="statusText" class="text-slate-300">Iniciando...</span>
        <span id="statusSpinner" class="animate-spin text-indigo-400">⚙️</span>
      </div>
    </section>

    <!-- Sección 2: Revisión y Edición de Momentos -->
    <section id="momentsSection" class="hidden bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex justify-between items-center">
        <div>
          <h2 class="text-lg font-bold text-slate-200">2. Revisa y Edita los Momentos Virales</h2>
          <p class="text-xs text-slate-400">Ajusta los segundos de inicio/fin (20-60s), el gancho o el título antes de renderizar.</p>
        </div>
        <button onclick="renderSelectedClips()" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2 px-5 rounded-lg text-sm shadow transition">
          Renderizar Clips Verticales 9:16
        </button>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border border-slate-700 rounded-lg">
          <thead class="bg-slate-700/70 text-slate-300 uppercase">
            <tr>
              <th class="p-3">#</th>
              <th class="p-3">Inicio (s)</th>
              <th class="p-3">Fin (s)</th>
              <th class="p-3">Duración</th>
              <th class="p-3">Título</th>
              <th class="p-3">Gancho (Hook inicial)</th>
              <th class="p-3">Score</th>
            </tr>
          </thead>
          <tbody id="momentsTableBody" class="divide-y divide-slate-700">
          </tbody>
        </table>
      </div>
    </section>

    <!-- Sección 3: Resultados y Descargas -->
    <section id="resultsSection" class="hidden bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-xl space-y-6">
      <h2 class="text-lg font-bold text-slate-200">3. Resultados y Entregables</h2>
      
      <!-- Clips generados -->
      <div>
        <h3 class="text-sm font-semibold text-indigo-300 uppercase mb-3">Clips Verticales 9:16 Generados (Subtítulos Quemados + Audio Normalizado):</h3>
        <div id="clipsGrid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        </div>
      </div>

      <!-- Paquete de YouTube -->
      <div class="border-t border-slate-700 pt-4">
        <div class="flex justify-between items-center mb-2">
          <h3 class="text-sm font-semibold text-rose-300 uppercase">Paquete de YouTube (Capítulos, Títulos, Descripción, Tags):</h3>
          <a id="downloadYtBtn" href="/api/download/youtube_package.md" class="text-xs bg-slate-700 hover:bg-slate-600 text-white py-1 px-3 rounded">Descargar .md</a>
        </div>
        <pre id="youtubePkgPreview" class="bg-slate-950 p-4 rounded-xl border border-slate-700 text-xs text-slate-300 overflow-x-auto max-h-80"></pre>
      </div>
    </section>

  </div>

  <script>
    let selectedFile = null;
    let currentHighlights = [];

    function handleFileSelected(e) {
      if (e.target.files && e.target.files[0]) {
        selectedFile = e.target.files[0];
        document.getElementById('fileLabel').innerText = 'Archivo seleccionado: ' + selectedFile.name;
      }
    }

    function setStatus(msg, loading = true) {
      const box = document.getElementById('statusAlert');
      const text = document.getElementById('statusText');
      const spinner = document.getElementById('statusSpinner');
      box.classList.remove('hidden');
      text.innerText = msg;
      spinner.style.display = loading ? 'inline-block' : 'none';
    }

    async function submitVideo() {
      const ytUrl = document.getElementById('youtubeUrl').value.trim();
      if (!selectedFile && !ytUrl) {
        alert('Por favor selecciona un archivo de video o ingresa una URL de YouTube.');
        return;
      }

      setStatus('Extrayendo audio y transcribiendo con faster-whisper...', true);
      document.getElementById('processBtn').disabled = true;

      const formData = new FormData();
      if (selectedFile) {
        formData.append('file', selectedFile);
      }
      if (ytUrl) {
        formData.append('youtube_url', ytUrl);
      }

      try {
        const resp = await fetch('/api/process', { method: 'POST', body: formData });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Error procesando el video');
        
        setStatus('Transcripción y detección de momentos completada.', false);
        currentHighlights = data.highlights;
        renderMomentsTable(currentHighlights);
        document.getElementById('momentsSection').classList.remove('hidden');
      } catch (err) {
        setStatus('Error: ' + err.message, false);
      } finally {
        document.getElementById('processBtn').disabled = false;
      }
    }

    function renderMomentsTable(highlights) {
      const tbody = document.getElementById('momentsTableBody');
      tbody.innerHTML = '';
      highlights.forEach((h, index) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-750 transition';
        tr.innerHTML = `
          <td class="p-3 font-bold">${h.id}</td>
          <td class="p-3"><input type="number" step="0.5" value="${h.start}" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-20 text-xs" onchange="updateMoment(${index}, 'start', this.value)"></td>
          <td class="p-3"><input type="number" step="0.5" value="${h.end}" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-20 text-xs" onchange="updateMoment(${index}, 'end', this.value)"></td>
          <td class="p-3 text-slate-400" id="dur_${index}">${(h.end - h.start).toFixed(1)}s</td>
          <td class="p-3"><input type="text" value="${h.title}" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-48 text-xs" onchange="updateMoment(${index}, 'title', this.value)"></td>
          <td class="p-3"><input type="text" value="${h.hook}" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-64 text-xs" onchange="updateMoment(${index}, 'hook', this.value)"></td>
          <td class="p-3 text-emerald-400 font-bold">${h.score}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function updateMoment(index, field, value) {
      if (field === 'start' || field === 'end') {
        currentHighlights[index][field] = parseFloat(value);
        currentHighlights[index].duration = currentHighlights[index].end - currentHighlights[index].start;
        const durCell = document.getElementById('dur_' + index);
        if (durCell) durCell.innerText = currentHighlights[index].duration.toFixed(1) + 's';
      } else {
        currentHighlights[index][field] = value;
      }
    }

    async function renderSelectedClips() {
      setStatus('Renderizando clips verticales 9:16 con subtítulos quemados y audio normalizado...', true);
      try {
        const resp = await fetch('/api/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ highlights: currentHighlights }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Error renderizando clips');

        setStatus('¡Renderizado completado con éxito!', false);
        document.getElementById('resultsSection').classList.remove('hidden');

        // Mostrar clips
        const grid = document.getElementById('clipsGrid');
        grid.innerHTML = '';
        data.clips.forEach(clipPath => {
          const filename = clipPath.split(/[\\\\/]/).pop();
          const card = document.createElement('div');
          card.className = 'bg-slate-900 border border-slate-700 rounded-xl p-3 flex flex-col justify-between space-y-2';
          card.innerHTML = `
            <video src="/api/download/${filename}" controls class="w-full rounded-lg aspect-[9/16] bg-black object-cover"></video>
            <div class="text-xs truncate font-medium text-slate-300">${filename}</div>
            <a href="/api/download/${filename}" download class="w-full block text-center bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-1.5 px-3 rounded text-xs transition">
              Descargar Clip MP4
            </a>
          `;
          grid.appendChild(card);
        });

        // Mostrar paquete youtube
        if (data.youtube_package_content) {
          document.getElementById('youtubePkgPreview').innerText = data.youtube_package_content;
        }

      } catch (err) {
        setStatus('Error en renderizado: ' + err.message, false);
      }
    }
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Devuelve la interfaz de usuario en HTML responsivo."""
    return HTML_TEMPLATE.replace("__YOUTUBE_NOTICE__", YOUTUBE_NOTICE)


@app.post("/api/process")
async def process_video(
    file: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
    model: str = Form("small"),
    no_llm: bool = Form(False),
):
    """Sube un video o descarga de YouTube y genera transcripción y momentos destacados."""
    target_video: Optional[Path] = None

    if file and file.filename:
        safe_name = Path(file.filename).name
        target_video = UPLOADS_DIR / safe_name
        with open(target_video, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        state["status"] = f"Archivo subido: {safe_name}"
    elif youtube_url and is_youtube_url(youtube_url):
        state["status"] = "Descargando video de YouTube..."
        target_video = download_youtube_video(youtube_url, UPLOADS_DIR)
    else:
        raise HTTPException(status_code=400, detail="Debe proporcionar un archivo de video o una URL de YouTube válida.")

    state["video_path"] = target_video

    # Transcripción
    audio_path = target_video.with_suffix(".wav")
    extract_audio(target_video, audio_path)
    transcript = transcribe_audio(audio_path, model_size=model)
    state["transcript"] = transcript

    save_transcript_json(transcript, WORKSPACE_DIR / "transcript.json")
    save_transcript_srt(transcript, WORKSPACE_DIR / "transcript.srt")

    # Momentos virales
    if not no_llm:
        h_coll = select_moments_llm(transcript, video_file=target_video.name)
    else:
        h_coll = select_moments_heuristic(transcript, video_file=target_video.name)

    state["highlights"] = [h.model_dump() for h in h_coll.highlights]
    save_highlights_json(h_coll, WORKSPACE_DIR / "highlights.json")

    return {
        "status": "Transcripción y momentos listos",
        "video_name": target_video.name,
        "duration": transcript.duration,
        "highlights": state["highlights"],
    }


@app.post("/api/render")
async def render_clips(req: UpdateHighlightsRequest):
    """Renderiza clips verticales a partir de la lista de momentos editada por el usuario."""
    if not state.get("video_path") or not Path(state["video_path"]).exists():
        raise HTTPException(status_code=400, detail="No hay ningún video cargado para renderizar.")

    video_path = Path(state["video_path"])
    transcript = state.get("transcript")

    rendered = render_all_highlights(
        video_path=video_path,
        highlights=req.highlights,
        output_dir=CLIPS_DIR,
        transcript=transcript,
    )

    state["rendered_clips"] = [str(p) for p in rendered]

    # Generar paquete YouTube
    yt_pkg_path = WORKSPACE_DIR / "youtube_package.md"
    yt_content = ""
    if transcript:
        yt_content = generate_youtube_package(
            transcript=transcript,
            highlights=req.highlights,
            output_path=yt_pkg_path,
            video_topic=video_path.stem.replace("_", " ").title(),
        )
        state["youtube_package"] = str(yt_pkg_path)

    return {
        "status": "Clips renderizados exitosamente",
        "clips": state["rendered_clips"],
        "youtube_package_content": yt_content,
    }


@app.get("/api/download/{filename}")
def download_file(filename: str):
    """Descarga un clip o entregable generado."""
    safe_name = Path(filename).name
    # Buscar en clips o en workspace
    clip_path = CLIPS_DIR / safe_name
    if clip_path.exists():
        return FileResponse(clip_path, media_type="video/mp4", filename=safe_name)

    ws_path = WORKSPACE_DIR / safe_name
    if ws_path.exists():
        return FileResponse(ws_path, filename=safe_name)

    raise HTTPException(status_code=404, detail="Archivo no encontrado.")
