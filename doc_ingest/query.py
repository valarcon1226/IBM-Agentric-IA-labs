"""
query.py: Optional vectorstore queries with a multi-agent pipeline.

Modes:
  python query.py "question"   -> Direct query
  python query.py              -> Interactive session
"""
import sys
import logging

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from retriever.builder import RetrieverBuilder
from agents.workflow import AgentWorkflow


def run_query(question: str):
    """RAG query with full multi-agent pipeline."""
    retriever_builder = RetrieverBuilder()
    total = retriever_builder.get_document_count()

    if total == 0:
        logger.error("The vector store is empty. Please ingest documents first.")
        sys.exit(1)

    logger.warning(f"DocIngest — Multi-Agent Query | {total} chunks in ChromaDB")
    logger.warning(f"Question: {question}")
    logger.warning("Processing...")

    retriever = retriever_builder.build_retriever_from_vectorstore()
    workflow = AgentWorkflow()

    try:
        result = workflow.full_pipeline(question=question, retriever=retriever)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(" ANSWER:")
    print(f"{'-'*60}")
    print(result["draft_answer"])

    if result.get("verification_report"):
        print(f"\n{'-'*60}")
        print(" VERIFICATION:")
        print(result["verification_report"])
    print(f"{'='*60}\n")


def interactive_mode():
    """Interactive QA session."""
    retriever_builder = RetrieverBuilder()
    total = retriever_builder.get_document_count()

    if total == 0:
        logger.error("The vector store is empty. Please ingest documents first.")
        sys.exit(1)

    retriever = retriever_builder.build_retriever_from_vectorstore()
    workflow = AgentWorkflow()

    print(f"\n{'='*60}")
    print(f" DocIngest — Interactive Mode")
    print(f" {total} chunks in ChromaDB")
    print(f" Type 'exit' to quit")
    print(f"{'='*60}\n")

    while True:
        try:
            question = input("? Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if question.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if not question:
            continue

        print("Processing...\n")
        try:
            result = workflow.full_pipeline(question=question, retriever=retriever)
            print(f"\n{'-'*60}")
            print(" Answer:")
            print(result["draft_answer"])
            if result.get("verification_report"):
                print(f"\n Verification:")
                print(result["verification_report"])
            print(f"{'-'*60}\n")
        except Exception as e:
            logger.error(f"Error: {e}")


if __name__ == "__main__":
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    if len(sys.argv) == 1:
        interactive_mode()
    else:
        question = " ".join(sys.argv[1:])
        run_query(question)
