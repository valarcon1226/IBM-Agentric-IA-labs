"""
RetrieverBuilder: construye el retriever híbrido BM25 + ChromaDB vectorstore.
Adaptado del lab DocChat (builder.py) de IBM Skills Network.

CAMBIO PRINCIPAL vs. lab:
  - WatsonxEmbeddings → OllamaEmbeddings (nomic-embed-text, 100% local)
  - ChromaDB en modo PERSISTENTE (los vectores sobreviven entre sesiones)
  - Soporta ADD incremental: no borra los vectores existentes al agregar nuevos docs
"""
import logging
from typing import List

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
import chromadb

from config.settings import (
    CHROMA_DB_PATH,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    VECTOR_SEARCH_K,
    HYBRID_RETRIEVER_WEIGHTS,
)
from config.constants import CHROMA_COLLECTION_NAME

logger = logging.getLogger(__name__)


class RetrieverBuilder:
    """
    Construye un retriever híbrido que combina:
      - BM25: búsqueda léxica por palabras clave (rápida, exacta)
      - ChromaDB: búsqueda semántica por embeddings (contextual, fuzzy)

    El ChromaDB es PERSISTENTE: los embeddings se guardan en disco y
    se reusan entre sesiones. Solo se vectorizan documentos nuevos.
    """

    def __init__(self):
        logger.info(f"Inicializando OllamaEmbeddings con modelo: {OLLAMA_EMBED_MODEL}")
        self.embeddings = OllamaEmbeddings(
            model=OLLAMA_EMBED_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
        # Cliente persistente de ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        logger.info(f"ChromaDB persistente en: {CHROMA_DB_PATH}")

    def get_or_create_vectorstore(self) -> Chroma:
        """Obtiene el vectorstore existente o crea uno nuevo."""
        return Chroma(
            client=self.chroma_client,
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=self.embeddings,
        )

    def add_documents(self, docs: List) -> int:
        """
        Agrega documentos nuevos al vectorstore persistente.
        NO borra los documentos existentes.
        Retorna la cantidad de chunks agregados.
        """
        if not docs:
            logger.warning("No hay documentos para agregar al vectorstore.")
            return 0

        try:
            vectorstore = self.get_or_create_vectorstore()
            vectorstore.add_documents(docs)
            count = len(docs)
            logger.info(f" {count} chunks agregados al vectorstore ChromaDB.")
            return count
        except Exception as e:
            logger.error(f"Error al agregar documentos a ChromaDB: {e}")
            raise

    def build_hybrid_retriever(self, docs: List) -> EnsembleRetriever:
        """
        Construye un retriever híbrido desde una lista de chunks.
        - Usa para BM25: solo los docs provistos (en memoria)
        - Usa para vector: el ChromaDB persistente completo
        """
        if not docs:
            raise ValueError("No se pueden construir retrievers sin documentos.")

        try:
            # 1. Agregar docs al ChromaDB persistente
            vectorstore = self.get_or_create_vectorstore()
            vectorstore.add_documents(docs)
            logger.info("Docs agregados al vectorstore ChromaDB.")

            # 2. BM25 sobre los docs actuales (en memoria)
            bm25 = BM25Retriever.from_documents(docs)
            bm25.k = VECTOR_SEARCH_K
            logger.info("BM25 retriever creado.")

            # 3. Vector retriever desde ChromaDB
            vector_retriever = vectorstore.as_retriever(
                search_kwargs={"k": VECTOR_SEARCH_K}
            )
            logger.info("Vector retriever creado desde ChromaDB.")

            # 4. Combinar en EnsembleRetriever
            hybrid_retriever = EnsembleRetriever(
                retrievers=[bm25, vector_retriever],
                weights=HYBRID_RETRIEVER_WEIGHTS,
            )
            logger.info(" Hybrid retriever (BM25 + Vector) listo.")
            return hybrid_retriever

        except Exception as e:
            logger.error(f"Error al construir hybrid retriever: {e}")
            raise

    def build_retriever_from_vectorstore(self) -> EnsembleRetriever:
        """
        Construye un retriever solo desde el ChromaDB persistente (sin nuevos docs).
        Útil para consultas cuando ya se ingirió todo previamente.
        """
        try:
            vectorstore = self.get_or_create_vectorstore()
            # Obtener todos los docs almacenados para BM25
            stored = vectorstore.get()
            if not stored or not stored.get("documents"):
                raise ValueError("El vectorstore está vacío. Ingesta documentos primero.")

            from langchain_core.documents import Document
            all_docs = [
                Document(page_content=text, metadata=meta)
                for text, meta in zip(stored["documents"], stored["metadatas"])
            ]

            bm25 = BM25Retriever.from_documents(all_docs)
            bm25.k = VECTOR_SEARCH_K
            vector_retriever = vectorstore.as_retriever(
                search_kwargs={"k": VECTOR_SEARCH_K}
            )
            hybrid_retriever = EnsembleRetriever(
                retrievers=[bm25, vector_retriever],
                weights=HYBRID_RETRIEVER_WEIGHTS,
            )
            logger.info(f" Retriever cargado desde ChromaDB ({len(all_docs)} docs).")
            return hybrid_retriever

        except Exception as e:
            logger.error(f"Error al cargar retriever desde vectorstore: {e}")
            raise

    def get_document_count(self) -> int:
        """Retorna el número total de chunks almacenados en ChromaDB."""
        try:
            vectorstore = self.get_or_create_vectorstore()
            stored = vectorstore.get()
            return len(stored.get("documents", []))
        except Exception:
            return 0
