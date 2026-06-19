# IBM RAG and Agentic AI Certification - Portfolio

This repository contains the practical projects and labs completed during the **IBM RAG and Agentic AI** certification program. The projects focus on implementing Vector Databases, Text Embeddings, and Similarity Search using Python.

## Projects Included

### 1. Grocery Store Similarity Search (`similarity_search_chromadb.py`)
A foundational project demonstrating how to use **Chroma DB** to perform semantic searches on text data. It uses `SentenceTransformers` to convert a list of grocery items into vector embeddings and retrieves the most relevant items based on natural language queries like "red" or "fresh".

**Technologies Used:** Chroma DB, HuggingFace Sentence Transformers (all-MiniLM-L6-v2)

### 2. HR Employee Advanced Search (`similarity_employeedata.py`)
An advanced implementation of a Vector Database simulating a Human Resources application. This project demonstrates how to combine **Semantic Similarity Search** with exact **Metadata Filtering** to find ideal candidates (e.g., finding "senior Python developers" who also have "10+ years of experience" and live in specific "major tech cities").

**Technologies Used:** Chroma DB, Metadata Filtering, Vector Embeddings.

## Setup Instructions

To run these scripts locally, ensure you have Python 3.11+ installed, and run the following command to install the required dependencies:

```bash
pip install chromadb==1.0.12 sentence-transformers==4.1.0 torch --index-url https://download.pytorch.org/whl/cpu
```

Then, you can execute any of the scripts:
```bash
python similarity_employeedata.py
```
