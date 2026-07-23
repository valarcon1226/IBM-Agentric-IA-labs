"""
ResearchAgent: genera respuestas basadas en documentos recuperados.
Adaptado del lab DocChat (research_agent.py).

CAMBIO PRINCIPAL vs. lab:
  - ibm_watsonx_ai.ModelInference → langchain_ollama.ChatOllama (100% local)
"""
import logging
from typing import Dict, List

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    LLM_TEMPERATURE_RESEARCH,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Genera una respuesta inicial (draft) basada en los documentos recuperados.
    Usa Ollama local en lugar de IBM WatsonX.
    """

    def __init__(self):
        logger.info(f"Inicializando ResearchAgent con Ollama ({OLLAMA_LLM_MODEL})")
        self.llm = ChatOllama(
            model=OLLAMA_LLM_MODEL,
            temperature=LLM_TEMPERATURE_RESEARCH,
            base_url=OLLAMA_BASE_URL,
            num_predict=LLM_MAX_TOKENS,
        )

    def generate_prompt(self, question: str, context: str) -> str:
        return f"""Eres un asistente de IA diseñado para dar respuestas precisas y factuales basadas en el contexto dado.

**Instrucciones:**
- Responde la siguiente pregunta usando ÚNICAMENTE el contexto proporcionado.
- Sé claro, conciso y factual.
- Devuelve toda la información relevante que puedas extraer del contexto.
- Si el contexto no es suficiente, dilo explícitamente.

**Pregunta:** {question}

**Contexto:**
{context}

**Tu respuesta:**"""

    def generate(self, question: str, documents: List[Document]) -> Dict:
        """
        Genera una respuesta draft usando los documentos recuperados.
        Retorna: dict con 'draft_answer' y 'context_used'.
        """
        logger.info(f"ResearchAgent.generate → pregunta: '{question}' | docs: {len(documents)}")

        context = "\n\n".join([doc.page_content for doc in documents])
        prompt = self.generate_prompt(question, context)

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            draft_answer = response.content.strip()
            logger.info(f"ResearchAgent generó respuesta ({len(draft_answer)} chars)")
        except Exception as e:
            logger.error(f"Error en ResearchAgent LLM: {e}")
            draft_answer = "No pude generar una respuesta debido a un error del modelo."

        if not draft_answer:
            draft_answer = "No puedo responder esta pregunta con los documentos disponibles."

        return {
            "draft_answer": draft_answer,
            "context_used": context,
        }
