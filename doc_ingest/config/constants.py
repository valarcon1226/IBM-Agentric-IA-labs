"""
Constantes del proyecto DocIngest.
"""

# Tipos de archivo aceptados para ingesta
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# ── Límite de tamaño de archivos ─────────────────────────────────────────────
# 1 GB: soporta documentos académicos de 1500+ páginas con imágenes y tablas.
# Un PDF académico denso de 1500 pgs suele pesar entre 100-600 MB.
MAX_TOTAL_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB
MAX_SINGLE_FILE_SIZE = 500 * 1024 * 1024  # 500 MB por archivo individual

# ── Chunking ──────────────────────────────────────────────────────────────────
# Para documentos muy largos, si el splitter por headers genera chunks enormes
# se aplica un splitter de respaldo por tamaño.
MAX_CHUNK_SIZE = 2000      # chars por chunk (respaldo)
CHUNK_OVERLAP = 200        # solapamiento entre chunks consecutivos

# Headers de Markdown para chunking estructurado
MARKDOWN_HEADERS = [("# ", "Header 1"), ("## ", "Header 2"), ("### ", "Header 3")]

# ── ChromaDB ──────────────────────────────────────────────────────────────────
# Nombre de la colección en ChromaDB
CHROMA_COLLECTION_NAME = "doc_ingest_collection"
