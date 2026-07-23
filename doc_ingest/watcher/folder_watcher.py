"""
FolderWatcher: monitorea carpeta e ingesta documentos automáticamente.
ACTUALIZADO: ahora incluye extracción de metadatos + exportación a Obsidian.
No requiere preguntas — ingesta sola. Las consultas son opcionales (query.py).

Pipeline completo al detectar un archivo:
  1. Docling → parsea y extrae texto estructurado
  2. MarkdownSplitter (+fallback) → chunks
  3. MetadataExtractor (Ollama) → título, resumen, tags, temas, entidades
  4. RetrieverBuilder → vectoriza y guarda en ChromaDB persistente
  5. ObsidianExporter → genera nota .md en el vault de Obsidian
"""
import logging
import time
from pathlib import Path
from typing import Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from document_processor.file_handler import DocumentProcessor
from retriever.builder import RetrieverBuilder
from extractor.metadata_extractor import MetadataExtractor
from exporter.obsidian_exporter import ObsidianExporter
from config.settings import WATCH_FOLDER
from config.constants import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)


class DocumentIngestionHandler(FileSystemEventHandler):
    """
    Manejador de eventos: se ejecuta cuando aparece/cambia un archivo
    en la carpeta vigilada. Lanza el pipeline de ingesta completo.
    """

    def __init__(
        self,
        processor: DocumentProcessor,
        retriever_builder: RetrieverBuilder,
        extractor: MetadataExtractor,
        exporter: ObsidianExporter,
        base_watch_path: str,
    ):
        super().__init__()
        self.processor = processor
        self.retriever_builder = retriever_builder
        self.extractor = extractor
        self.exporter = exporter
        self.base_watch_path = Path(base_watch_path)
        self._processing: Set[str] = set()

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent) or event.is_directory:
            return
        self._handle_file(event.src_path, action="NUEVO")

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent) or event.is_directory:
            return
        self._handle_file(event.src_path, action="ACTUALIZADO")

    def _handle_file(self, file_path: str, action: str):
        path = Path(file_path)
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return
        if file_path in self._processing:
            return

        self._processing.add(file_path)
        try:
            self._run_ingestion_pipeline(file_path, action)
        except Exception as e:
            logger.error(f"Error procesando {path.name}: {e}")
            logger.error(f"Error en pipeline de ingesta de {file_path}: {e}", exc_info=True)
        finally:
            time.sleep(2)
            self._processing.discard(file_path)

    def _run_ingestion_pipeline(self, file_path: str, action: str):
        """Ejecuta el pipeline completo de ingesta para un archivo."""
        path = Path(file_path)
        start_time = time.time()

        logger.info(f"[{action}] {path.name}")

        # Esperar a que el archivo esté completamente escrito
        time.sleep(1.5)

        # ── PASO 1: Parseo con Docling ────────────────────────────────────────
        logger.info("[1/4] Parseando con Docling...")
        chunks = self.processor.process_single(file_path)
        if not chunks:
            logger.warning("No se generaron chunks. El archivo puede estar corrupto o vacío.")
            return
        logger.info(f"    {len(chunks)} chunks generados")

        # ── PASO 2: Extracción de metadatos con Ollama ────────────────────────
        logger.info("[2/4] Extrayendo metadatos con Ollama...")
        metadata = self.extractor.extract(chunks, path.name)
        title = metadata.get("title", path.name)
        topics = metadata.get("topics", [])
        tags = metadata.get("tags", [])
        logger.info(f"    Título: {title}")
        logger.info(f"    Temas: {', '.join(topics[:3]) if topics else 'N/A'}")
        logger.info(f"    Tags: {', '.join(tags[:4]) if tags else 'N/A'}")

        # ── PASO 3: Vectorización en ChromaDB ────────────────────────────────
        logger.info("[3/4] Vectorizando con nomic-embed-text → ChromaDB...")
        count = self.retriever_builder.add_documents(chunks)
        total = self.retriever_builder.get_document_count()
        logger.info(f"    {count} chunks vectorizados | Total en ChromaDB: {total}")

        # ── PASO 4: Exportar nota a Obsidian ─────────────────────────────────
        logger.info("[4/4] Generando nota en Obsidian vault...")
        note_path = self.exporter.export_document(metadata, chunks, file_path, base_dir=self.base_watch_path)
        logger.info(f"    Nota creada: {note_path.name}")

        elapsed = time.time() - start_time
        logger.info(f"Ingesta completada en {elapsed:.1f}s")
        logger.info(f"Pipeline completado para {path.name} en {elapsed:.1f}s")


class FolderWatcher:
    """Watcher que mantiene el Observer activo hasta recibir Ctrl+C."""

    def __init__(self, watch_path: str = None):
        self.watch_path = watch_path or WATCH_FOLDER
        Path(self.watch_path).mkdir(parents=True, exist_ok=True)

        # Inicializar todos los componentes del pipeline
        self.processor = DocumentProcessor()
        self.retriever_builder = RetrieverBuilder()
        self.extractor = MetadataExtractor()
        self.exporter = ObsidianExporter()

        self.handler = DocumentIngestionHandler(
            processor=self.processor,
            retriever_builder=self.retriever_builder,
            extractor=self.extractor,
            exporter=self.exporter,
            base_watch_path=self.watch_path,
        )
        self.observer = Observer()

    def start(self):
        """Inicia el watcher. Bloquea hasta Ctrl+C."""
        self.observer.schedule(self.handler, path=self.watch_path, recursive=True)
        self.observer.start()

        vault_stats = self.exporter.get_vault_stats()
        total_chunks = self.retriever_builder.get_document_count()

        logger.info("DocIngest Watcher ACTIVO")
        logger.info(f"Vigilando:       {self.watch_path}")
        logger.info(f"ChromaDB chunks: {total_chunks}")
        logger.info(f"Notas Obsidian:  {vault_stats['total_notes']}")
        logger.info(f"Tipos aceptados: {', '.join(ALLOWED_EXTENSIONS)}")
        logger.info("Copia un documento a la carpeta para ingestarlo")
        logger.info("Para consultas:  python query.py")
        logger.info("Detener:         Ctrl+C")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Deteniendo watcher...")
            self.observer.stop()

        self.observer.join()
        logger.info("DocIngest detenido.")

    def stop(self):
        self.observer.stop()
        self.observer.join()
