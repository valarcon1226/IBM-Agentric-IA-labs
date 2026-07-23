"""
RelevanceChecker: determina si la pregunta es respondible con los documentos.
Adaptado del lab DocChat (relevance_checker.py).

CAMBIO PRINCIPAL vs. lab:
  - ibm_watsonx_ai.ModelInference → langchain_ollama.ChatOllama (100% local)
  - project_id="skills-network" eliminado
"""
import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from config.settings import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL, LLM_TEMPERATURE_RELEVANCE

logger = logging.getLogger(__name__)


class RelevanceChecker:
    """
    Clasifica si los documentos recuperados pueden responder la pregunta del usuario.
    Retorna: "CAN_ANSWER", "PARTIAL" o "NO_MATCH".
    """

    def __init__(self):
        logger.info(f"Inicializando RelevanceChecker con Ollama ({OLLAMA_LLM_MODEL})")
        self.llm = ChatOllama(
            model=OLLAMA_LLM_MODEL,
            temperature=LLM_TEMPERATURE_RELEVANCE,
            base_url=OLLAMA_BASE_URL,
        )

    def check(self, question: str, retriever, k: int = 20) -> str:
        """
        1. Recupera los top-k chunks desde el retriever.
        2. Los combina en un string de contexto.
        3. Pregunta al LLM local si puede responder con ese contexto.

        Retorna: "CAN_ANSWER", "PARTIAL" o "NO_MATCH"
        """
        logger.debug(f"RelevanceChecker.check → pregunta: '{question}'")

        # Recuperar chunks
        top_docs = retriever.invoke(question)
        if not top_docs:
            logger.debug("No se recuperaron documentos → NO_MATCH")
            return "NO_MATCH"

        document_content = "\n\n".join(doc.page_content for doc in top_docs[:k])

        prompt = f"""Eres un verificador de relevancia entre una pregunta de usuario y el contenido de documentos.

**Instrucciones:**
- Clasifica qué tan bien el contenido del documento responde la pregunta.
- Responde ÚNICAMENTE con una de estas etiquetas: CAN_ANSWER, PARTIAL, NO_MATCH
- No añadas ninguna explicación adicional.

**Etiquetas:**
1) "CAN_ANSWER": Los fragmentos contienen suficiente información explícita para responder completamente.
2) "PARTIAL": Los fragmentos mencionan el tema pero no tienen todos los detalles necesarios.
3) "NO_MATCH": Los fragmentos no hablan del tema de la pregunta en absoluto.

**Pregunta:** {question}
**Fragmentos del documento:**
{document_content}

**Responde SOLO con: CAN_ANSWER, PARTIAL o NO_MATCH**"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            llm_response = response.content.strip().upper()
            logger.debug(f"RelevanceChecker respuesta LLM: {llm_response}")
        except Exception as e:
            logger.error(f"Error en RelevanceChecker LLM: {e}")
            return "NO_MATCH"

        # Validar la respuesta
        valid_labels = {"CAN_ANSWER", "PARTIAL", "NO_MATCH"}
        # Buscar el label en la respuesta (a veces el modelo añade texto extra)
        for label in valid_labels:
            if label in llm_response:
                logger.debug(f"Clasificación: {label}")
                return label

        logger.debug("Label no reconocido → NO_MATCH por defecto")
        return "NO_MATCH"
