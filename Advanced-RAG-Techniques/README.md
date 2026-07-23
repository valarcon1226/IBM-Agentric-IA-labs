# Advanced RAG Techniques

This project demonstrates advanced Retrieval-Augmented Generation (RAG) techniques using multiple frameworks:
- **FAISS**: For highly efficient semantic similarity search.
- **LangChain & Watsonx**: For vector store integrations (e.g., Chroma), document splitting, and LLM orchestration.
- **LlamaIndex**: For implementing advanced retrieval patterns such as vector search, BM25, and query fusion.

## Project Structure
- `main.py`: The entry point for executing the retrieval workflows.
- `tools.py`: Contains the refactored classes and utility functions encapsulating the logic for each framework.
- `requirements.txt`: Lists all Python dependencies required to run the project.

## Setup
1. Create a virtual environment.
2. Run `pip install -r requirements.txt`.
3. Execute `python main.py` to see the retrieval pipelines in action.
