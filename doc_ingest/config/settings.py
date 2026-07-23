"""
Configuración central del proyecto DocIngest.
Modifica estos valores según tu entorno local.
"""
from pathlib import Path

# ── Rutas del proyecto ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
WATCH_FOLDER = str(BASE_DIR / "watch_folder")    # Carpeta vigilada por el watcher
CHROMA_DB_PATH = str(BASE_DIR / "chroma_db")     # Vector store persistente en disco
CACHE_DIR = str(BASE_DIR / "cache")              # Caché de chunks procesados
LOG_FILE = str(BASE_DIR / "logs" / "ingest.log")
OBSIDIAN_VAULT_PATH = str(BASE_DIR / "obsidian_vault")  # Notas .md para Obsidian

# ── Ollama (LLM local) ────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_LLM_MODEL = "llama3.2"          # Alternativa: "mistral", "phi3"
OLLAMA_EMBED_MODEL = "nomic-embed-text" # Modelo de embeddings local

# ── Parámetros del LLM ────────────────────────────────────────────────────────
LLM_TEMPERATURE_RESEARCH = 0.3
LLM_TEMPERATURE_VERIFY = 0.0
LLM_TEMPERATURE_RELEVANCE = 0.0
LLM_MAX_TOKENS = 512

# ── Retriever ─────────────────────────────────────────────────────────────────
VECTOR_SEARCH_K = 5
HYBRID_RETRIEVER_WEIGHTS = [0.5, 0.5]  # [BM25, Vector]

# ── Procesamiento de documentos ───────────────────────────────────────────────
CACHE_EXPIRE_DAYS = 30
# Límite en MB (usado solo para logging/advertencias; el límite duro está en constants.py)
MAX_TOTAL_SIZE_MB = 1024   # 1 GB — soporta libros académicos de 1500+ páginas
