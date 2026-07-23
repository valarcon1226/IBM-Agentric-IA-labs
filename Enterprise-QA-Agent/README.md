# Enterprise QA Agent

A specialized Question-Answering (QA) agent designed to search through private corporate documents and provide accurate, synthesized answers to employees.

## Features
- **Private Document Ingestion**: Securely reads and chunks private text files and PDFs.
- **RAG Architecture**: Uses Retrieval-Augmented Generation to eliminate hallucinations and source all claims back to the original documents.
- **Interactive CLI**: Includes a conversational interface with memory to answer questions contextually.

## Tech Stack
- LangChain
- Large Language Models (LLMs) (Watsonx)
- Python
- ChromaDB

## Usage
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set your environment variable for Watsonx (if needed):
   ```bash
   export WATSONX_API_KEY="your_api_key"
   ```
3. Run the agent:
   ```bash
   python main.py
   ```
