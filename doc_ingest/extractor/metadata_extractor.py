"""
MetadataExtractor: extrae información estructurada de documentos usando Ollama.
MÓDULO NUEVO — no existe en el lab DocChat original.

Para cada documento ingresado, usa llama3.2 local para extraer:
  - Título
  - Resumen (3-5 líneas)
  - Temas principales
  - Tags / palabras clave
  - Tipo de documento
  - Idioma
  - Entidades clave (personas, organizaciones, fechas)

Estrategia para documentos largos:
  - No pasa el documento completo al LLM (excedería el contexto)
  - Toma una muestra representativa: primeros N + últimos N chunks
  - Suficiente para capturar título, abstract, conclusiones y temas
"""
import json
import logging
from typing import Dict, List

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from config.settings import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL

logger = logging.getLogger(__name__)

# Cuántos chunks del inicio y final del doc usar para la extracción
# (evita exceder el contexto del LLM en docs de 1500 páginas)
SAMPLE_CHUNKS_FROM_START = 8
SAMPLE_CHUNKS_FROM_END = 4


class MetadataExtractor:
    """
    Usa Ollama local para extraer metadatos estructurados de un documento.
    Funciona con documentos de cualquier tamaño porque solo muestrea
    una porción representativa (inicio + final).
    """

    def __init__(self):
        logger.info(f"Inicializando MetadataExtractor con Ollama ({OLLAMA_LLM_MODEL})")
        self.llm = ChatOllama(
            model=OLLAMA_LLM_MODEL,
            temperature=0.1,      # Baja temperatura para respuestas consistentes
            base_url=OLLAMA_BASE_URL,
            format="json",        # Forzar salida JSON estructurada
        )

    def extract(self, chunks: List[Document], file_name: str) -> Dict:
        """
        Extrae metadatos de una lista de chunks.
        Retorna un diccionario con título, resumen, temas, tags, etc.
        """
        if not chunks:
            return self._empty_metadata(file_name)

        # Muestra representativa: inicio + final del documento
        sample = self._get_representative_sample(chunks)
        context = "\n\n---\n\n".join([c.page_content for c in sample])

        prompt = f"""Analiza el siguiente contenido de un documento y extrae metadatos estructurados.
Responde ÚNICAMENTE con un JSON válido, sin texto adicional.

Contenido del documento (fragmentos representativos):
{context}

Responde con este JSON exacto:
{{
  "title": "título del documento (en el idioma original)",
  "summary": "resumen de 3 a 5 líneas del contenido principal",
  "topics": ["tema1", "tema2", "tema3"],
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "doc_type": "uno de: research_paper, report, book, manual, article, thesis, contract, other",
  "language": "idioma principal del documento: español, english, etc.",
  "key_entities": {{
    "people": ["persona1", "persona2"],
    "organizations": ["org1", "org2"],
    "dates": ["fecha1", "fecha2"],
    "places": ["lugar1", "lugar2"]
  }}
}}"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            raw = response.content.strip()

            # Intentar parsear el JSON
            # A veces el modelo añade ```json ... ``` o texto antes/después
            raw = self._clean_json_response(raw)
            metadata = json.loads(raw)
            logger.info(f"Metadatos extraídos de '{file_name}': {list(metadata.keys())}")
            return metadata

        except json.JSONDecodeError as e:
            logger.warning(f"Error parseando JSON de metadatos para '{file_name}': {e}")
            return self._fallback_extraction(chunks, file_name)
        except Exception as e:
            logger.error(f"Error en MetadataExtractor para '{file_name}': {e}")
            return self._empty_metadata(file_name)

    def _get_representative_sample(self, chunks: List[Document]) -> List[Document]:
        """
        Selecciona chunks representativos del inicio y final del documento.
        Para docs de 1500 páginas con miles de chunks, esto es esencial
        para no exceder el contexto del LLM.
        """
        total = len(chunks)
        if total <= (SAMPLE_CHUNKS_FROM_START + SAMPLE_CHUNKS_FROM_END):
            return chunks  # Doc pequeño: usar todos

        start_chunks = chunks[:SAMPLE_CHUNKS_FROM_START]
        end_chunks = chunks[-SAMPLE_CHUNKS_FROM_END:]
        return start_chunks + end_chunks

    def _clean_json_response(self, text: str) -> str:
        """Limpia la respuesta del LLM para extraer solo el JSON."""
        # Remover bloques ```json ... ```
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    def _empty_metadata(self, file_name: str) -> Dict:
        """Retorna metadatos vacíos cuando no se puede extraer nada."""
        return {
            "title": file_name.replace("_", " ").replace("-", " "),
            "summary": "No se pudo extraer resumen automáticamente.",
            "topics": [],
            "tags": [],
            "doc_type": "other",
            "language": "unknown",
            "key_entities": {"people": [], "organizations": [], "dates": [], "places": []}
        }

    def _fallback_extraction(self, chunks: List[Document], file_name: str) -> Dict:
        """
        Extracción simplificada si el JSON falla.
        Solo extrae el título con una llamada más simple.
        """
        try:
            first_content = chunks[0].page_content[:500] if chunks else ""
            simple_prompt = f"""Del siguiente texto, responde solo con el título del documento:
{first_content}
Título:"""
            self.llm.format = None  # Desactivar modo JSON para esta llamada
            response = self.llm.invoke([HumanMessage(content=simple_prompt)])
            title = response.content.strip().split("\n")[0]
        except Exception:
            title = file_name

        result = self._empty_metadata(file_name)
        result["title"] = title
        return result
