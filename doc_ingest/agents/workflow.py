"""
AgentWorkflow: orquesta el pipeline multi-agente con LangGraph.
Tomado directamente del lab DocChat (workflow.py).
No requiere cambios: LangGraph es agnóstico al proveedor de LLM.
"""
import logging
from typing import TypedDict, List, Dict

from langgraph.graph import StateGraph, END
from langchain_core.documents import Document
from langchain_classic.retrievers import EnsembleRetriever

from agents.relevance_checker import RelevanceChecker
from agents.research_agent import ResearchAgent
from agents.verification_agent import VerificationAgent

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    question: str
    documents: List[Document]
    draft_answer: str
    verification_report: str
    is_relevant: bool
    retriever: EnsembleRetriever


class AgentWorkflow:
    """
    Workflow multi-agente con LangGraph:
      1. check_relevance → determina si la pregunta es respondible
      2. research        → genera respuesta draft
      3. verify          → verifica la respuesta
      4. (loop)          → si falla verificación, vuelve a research
    """

    def __init__(self):
        self.researcher = ResearchAgent()
        self.verifier = VerificationAgent()
        self.relevance_checker = RelevanceChecker()
        self.compiled_workflow = self._build_workflow()
        logger.info("AgentWorkflow compilado y listo.")

    def _build_workflow(self):
        workflow = StateGraph(AgentState)

        # Nodos
        workflow.add_node("check_relevance", self._check_relevance_step)
        workflow.add_node("research", self._research_step)
        workflow.add_node("verify", self._verification_step)

        # Edges
        workflow.set_entry_point("check_relevance")
        workflow.add_conditional_edges(
            "check_relevance",
            self._decide_after_relevance_check,
            {"relevant": "research", "irrelevant": END},
        )
        workflow.add_edge("research", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._decide_next_step,
            {"re_research": "research", "end": END},
        )
        return workflow.compile()

    def _check_relevance_step(self, state: AgentState) -> Dict:
        retriever = state["retriever"]
        classification = self.relevance_checker.check(
            question=state["question"],
            retriever=retriever,
            k=20,
        )
        if classification in ("CAN_ANSWER", "PARTIAL"):
            return {"is_relevant": True}
        return {
            "is_relevant": False,
            "draft_answer": (
                "Esta pregunta no está relacionada con los documentos disponibles. "
                "Por favor reformula tu pregunta."
            ),
        }

    def _decide_after_relevance_check(self, state: AgentState) -> str:
        decision = "relevant" if state["is_relevant"] else "irrelevant"
        logger.debug(f"Relevance decision: {decision}")
        return decision

    def _research_step(self, state: AgentState) -> Dict:
        logger.debug("Ejecutando research step...")
        result = self.researcher.generate(state["question"], state["documents"])
        return {"draft_answer": result["draft_answer"]}

    def _verification_step(self, state: AgentState) -> Dict:
        logger.debug("Ejecutando verification step...")
        result = self.verifier.check(state["draft_answer"], state["documents"])
        return {"verification_report": result["verification_report"]}

    def _decide_next_step(self, state: AgentState) -> str:
        report = state["verification_report"]
        if "Supported: NO" in report or "Relevant: NO" in report:
            logger.info("Verificación fallida → re-research")
            return "re_research"
        logger.info("Verificación exitosa → fin del workflow")
        return "end"

    def full_pipeline(self, question: str, retriever: EnsembleRetriever) -> Dict:
        """Ejecuta el pipeline completo y retorna la respuesta final."""
        logger.info(f"Iniciando full_pipeline para: '{question}'")
        documents = retriever.invoke(question)
        logger.info(f"Recuperados {len(documents)} documentos.")

        initial_state = AgentState(
            question=question,
            documents=documents,
            draft_answer="",
            verification_report="",
            is_relevant=False,
            retriever=retriever,
        )

        try:
            final_state = self.compiled_workflow.invoke(initial_state)
        except Exception as e:
            logger.error(f"Error en el workflow: {e}")
            raise

        return {
            "draft_answer": final_state.get("draft_answer", ""),
            "verification_report": final_state.get("verification_report", ""),
        }
