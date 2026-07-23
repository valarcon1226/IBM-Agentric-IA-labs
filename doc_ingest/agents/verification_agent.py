"""
VerificationAgent: verifica la respuesta generada contra los documentos fuente.
Adaptado del lab DocChat (verification_agent.py).

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
    LLM_TEMPERATURE_VERIFY,
)

logger = logging.getLogger(__name__)


class VerificationAgent:
    """
    Verifica si la respuesta generada está respaldada por los documentos fuente.
    Detecta alucinaciones, afirmaciones sin soporte y contradicciones.
    """

    def __init__(self):
        logger.info(f"Inicializando VerificationAgent con Ollama ({OLLAMA_LLM_MODEL})")
        self.llm = ChatOllama(
            model=OLLAMA_LLM_MODEL,
            temperature=LLM_TEMPERATURE_VERIFY,
            base_url=OLLAMA_BASE_URL,
        )

    def generate_prompt(self, answer: str, context: str) -> str:
        return f"""Eres un asistente de IA que verifica la exactitud y relevancia de respuestas contra un contexto dado.

**Instrucciones:**
- Verifica la siguiente respuesta contra el contexto proporcionado.
- Evalúa:
  1. ¿Está la respuesta respaldada por el contexto? (SÍ/NO)
  2. ¿Hay afirmaciones sin soporte? (lista si hay)
  3. ¿Hay contradicciones con el contexto? (lista si hay)
  4. ¿Es relevante la respuesta a la pregunta? (SÍ/NO)
- Responde ÚNICAMENTE con el formato especificado abajo.

**Formato de respuesta:**
Supported: YES/NO
Unsupported Claims: [elemento1, elemento2, ...] o []
Contradictions: [elemento1, elemento2, ...] o []
Relevant: YES/NO
Additional Details: [detalles adicionales o "None"]

**Respuesta a verificar:**
{answer}

**Contexto:**
{context}

**Responde SOLO con el formato indicado arriba:**"""

    def parse_verification_response(self, response_text: str) -> Dict:
        """Parsea la respuesta estructurada del LLM en un diccionario."""
        result = {
            "Supported": "NO",
            "Unsupported Claims": [],
            "Contradictions": [],
            "Relevant": "NO",
            "Additional Details": "",
        }
        try:
            lines = response_text.strip().split("\n")
            for line in lines:
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                if key == "Supported":
                    result["Supported"] = "YES" if "YES" in value.upper() else "NO"
                elif key == "Unsupported Claims":
                    result["Unsupported Claims"] = self._parse_list(value)
                elif key == "Contradictions":
                    result["Contradictions"] = self._parse_list(value)
                elif key == "Relevant":
                    result["Relevant"] = "YES" if "YES" in value.upper() else "NO"
                elif key == "Additional Details":
                    result["Additional Details"] = value if value.lower() != "none" else ""
        except Exception as e:
            logger.warning(f"Error parseando respuesta de verificación: {e}")

        return result

    def _parse_list(self, value: str) -> List[str]:
        """Parsea un string tipo [item1, item2] en una lista Python."""
        value = value.strip("[]").strip()
        if not value:
            return []
        return [item.strip().strip('"').strip("'") for item in value.split(",") if item.strip()]

    def format_verification_report(self, verification: Dict) -> str:
        """Formatea el dict de verificación en un reporte legible."""
        supported = verification.get("Supported", "NO")
        unsupported = verification.get("Unsupported Claims", [])
        contradictions = verification.get("Contradictions", [])
        relevant = verification.get("Relevant", "NO")
        details = verification.get("Additional Details", "")

        report = f"**Supported:** {supported}\n"
        report += f"**Unsupported Claims:** {', '.join(unsupported) if unsupported else 'None'}\n"
        report += f"**Contradictions:** {', '.join(contradictions) if contradictions else 'None'}\n"
        report += f"**Relevant:** {relevant}\n"
        if details:
            report += f"**Additional Details:** {details}\n"
        return report

    def check(self, answer: str, documents: List[Document]) -> Dict:
        """
        Verifica la respuesta contra los documentos fuente.
        Retorna: dict con 'verification_report' y 'context_used'.
        """
        logger.info(f"VerificationAgent.check → answer ({len(answer)} chars), docs: {len(documents)}")

        context = "\n\n".join([doc.page_content for doc in documents])
        prompt = self.generate_prompt(answer, context)

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            llm_response = response.content.strip()
        except Exception as e:
            logger.error(f"Error en VerificationAgent LLM: {e}")
            llm_response = ""

        if not llm_response:
            verification_dict = {
                "Supported": "NO",
                "Unsupported Claims": [],
                "Contradictions": [],
                "Relevant": "NO",
                "Additional Details": "Error: el modelo no devolvió respuesta.",
            }
        else:
            verification_dict = self.parse_verification_response(llm_response)

        report = self.format_verification_report(verification_dict)
        logger.info(f"Verification report generado:\n{report}")

        return {
            "verification_report": report,
            "context_used": context,
        }
