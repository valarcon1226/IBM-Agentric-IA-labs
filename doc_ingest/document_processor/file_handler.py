"""
DocumentProcessor: parseo, chunking y caché de documentos.
Basado en el lab DocChat (file_handler.py) de IBM Skills Network.
Adaptado para uso standalone sin dependencias de WatsonX.
Soporta documentos académicos de 1500+ páginas (hasta 1 GB).
"""
import os
import hashlib
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from docling.document_converter import DocumentConverter
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from config import constants
from config.constants import ALLOWED_EXTENSIONS, MAX_SINGLE_FILE_SIZE, MAX_CHUNK_SIZE, CHUNK_OVERLAP
from config.settings import CACHE_DIR, CACHE_EXPIRE_DAYS

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Procesa documentos en tres pasos:
      1. Validación de archivos
      2. Conversión a Markdown con Docling (OCR incluido)
      3. Chunking estructurado por headers
    Incluye caché por hash SHA-256 para evitar reprocesar documentos ya vistos.
    """

    def __init__(self):
        self.headers = [("# ", "Header 1"), ("## ", "Header 2"), ("### ", "Header 3")]
        self.cache_dir = Path(CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DocumentProcessor inicializado. Caché en: {self.cache_dir}")

    def validate_file(self, file_path: str) -> bool:
        """Valida extensión y tamaño de un archivo individual."""
        path = Path(file_path)
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.warning(f"Tipo no soportado: {path.suffix} → {file_path}")
            return False
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_bytes > MAX_SINGLE_FILE_SIZE:
            logger.warning(f"Archivo demasiado grande ({size_mb:.1f} MB > 500 MB): {file_path}")
            return False
        logger.info(f"Archivo válido: {path.name} ({size_mb:.1f} MB)")
        return True

    def process(self, file_paths: List[str]) -> List:
        """
        Procesa una lista de rutas de archivos.
        Retorna una lista de chunks (LangChain Documents) únicos.
        """
        all_chunks = []
        seen_hashes = set()

        for file_path in file_paths:
            if not self.validate_file(file_path):
                continue
            try:
                with open(file_path, "rb") as f:
                    file_hash = self._generate_hash(f.read())

                cache_path = self.cache_dir / f"{file_hash}.pkl"

                if self._is_cache_valid(cache_path):
                    logger.info(f"Cargando desde caché: {file_path}")
                    chunks = self._load_from_cache(cache_path)
                else:
                    logger.info(f"Procesando con Docling: {file_path}")
                    chunks = self._process_file(file_path)
                    if chunks:
                        self._save_to_cache(chunks, cache_path)

                # Deduplicar chunks
                for chunk in chunks:
                    chunk_hash = self._generate_hash(chunk.page_content.encode())
                    if chunk_hash not in seen_hashes:
                        all_chunks.append(chunk)
                        seen_hashes.add(chunk_hash)

            except Exception as e:
                logger.error(f"Error procesando {file_path}: {e}")
                continue

        logger.info(f"Total chunks únicos procesados: {len(all_chunks)}")
        return all_chunks

    def process_single(self, file_path: str) -> List:
        """Procesa un único archivo. Útil para el watcher."""
        return self.process([file_path])

    def _process_file(self, file_path: str) -> List:
        """Convierte el documento a Markdown con Docling y lo divide en chunks.
        
        Para documentos muy largos (1500+ páginas), usa un splitter de respaldo
        para asegurar que ningún chunk supere MAX_CHUNK_SIZE caracteres.
        """
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            logger.info(f"Iniciando Docling en {Path(file_path).name} ({size_mb:.1f} MB)...")
            logger.info(f"   📖 Docling procesando {Path(file_path).name} ({size_mb:.1f} MB) — puede tardar varios minutos para docs grandes...")

            converter = DocumentConverter()
            result = converter.convert(file_path)
            markdown_content = result.document.export_to_markdown()
            logger.info(f"Docling completó. Markdown generado: {len(markdown_content):,} caracteres")

            # 1º intento: chunking por headers (preserva estructura del doc)
            splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=self.headers,
                strip_headers=False
            )
            chunks = splitter.split_text(markdown_content)

            # 2º intento de respaldo: si hay chunks muy grandes, subdivide más
            # Esto es crítico para documentos académicos sin muchos headers
            oversized = [c for c in chunks if len(c.page_content) > MAX_CHUNK_SIZE]
            if oversized:
                logger.info(f"{len(oversized)} chunks grandes detectados → aplicando RecursiveCharacterTextSplitter")
                fallback_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=MAX_CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                refined_chunks = []
                for chunk in chunks:
                    if len(chunk.page_content) > MAX_CHUNK_SIZE:
                        sub_chunks = fallback_splitter.create_documents(
                            [chunk.page_content],
                            metadatas=[chunk.metadata]
                        )
                        refined_chunks.extend(sub_chunks)
                    else:
                        refined_chunks.append(chunk)
                chunks = refined_chunks
                logger.info(f"Chunks tras subdivisión: {len(chunks)}")

            # Agregar metadata de origen a cada chunk
            for chunk in chunks:
                chunk.metadata["source"] = file_path
                chunk.metadata["file_name"] = Path(file_path).name
                chunk.metadata["ingested_at"] = datetime.now().isoformat()

            logger.info(f"Total chunks generados de {Path(file_path).name}: {len(chunks)}")
            return chunks

        except Exception as e:
            logger.error(f"Error en Docling al procesar {file_path}: {e}")
            return []

    def _generate_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _save_to_cache(self, chunks: List, cache_path: Path):
        with open(cache_path, "wb") as f:
            pickle.dump({
                "timestamp": datetime.now().timestamp(),
                "chunks": chunks
            }, f)
        logger.debug(f"Caché guardado: {cache_path}")

    def _load_from_cache(self, cache_path: Path) -> List:
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        return data["chunks"]

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return cache_age < timedelta(days=CACHE_EXPIRE_DAYS)
