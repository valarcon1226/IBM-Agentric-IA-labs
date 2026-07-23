"""
ingest.py: standalone script for manual document ingestion.
Usage:
  python ingest.py path/to/document.pdf
  python ingest.py path/to/folder/
  python ingest.py doc1.pdf doc2.docx doc3.txt
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

from document_processor.file_handler import DocumentProcessor
from retriever.builder import RetrieverBuilder
from config.constants import ALLOWED_EXTENSIONS


def ingest_paths(paths: list[str]):
    """Ingests a list of paths (files or directories)."""
    processor = DocumentProcessor()
    retriever_builder = RetrieverBuilder()

    all_files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for ext in ALLOWED_EXTENSIONS:
                all_files.extend([str(f) for f in path.glob(f"**/*{ext}")])
        elif path.is_file():
            all_files.append(str(path))
        else:
            logger.warning(f"Path not found: {p}")

    if not all_files:
        logger.error("No valid files found for ingestion.")
        sys.exit(1)

    logger.info(f"DocIngest — Manual Ingestion")
    logger.info(f"Files to process: {len(all_files)}")
    for f in all_files:
        logger.info(f"  -> {Path(f).name}")

    logger.info("Processing documents with Docling...")
    chunks = processor.process(all_files)

    if not chunks:
        logger.error("No chunks generated. Please check the files.")
        sys.exit(1)

    logger.info(f"{len(chunks)} chunks generated.")

    logger.info("Vectorizing and saving to ChromaDB...")
    count = retriever_builder.add_documents(chunks)
    total = retriever_builder.get_document_count()

    logger.info(f"Ingestion completed: Added {count} chunks. Total in ChromaDB: {total}")
    logger.info("You can now query using: python query.py \"your question here\"")


if __name__ == "__main__":
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    if len(sys.argv) < 2:
        logger.error("Usage: python ingest.py <file_or_folder_path> [...]")
        sys.exit(1)

    ingest_paths(sys.argv[1:])
