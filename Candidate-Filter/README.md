# Vector Database Book Search

This project demonstrates the usage of `chromadb` to build a vector database for semantic search and metadata filtering. It loads a collection of books, generates embeddings using `SentenceTransformers`, and performs intelligent similarity searches across the book catalog.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the main script:
   ```bash
   python main.py
   ```

## Features

- **Semantic Search**: Find books based on semantic meaning rather than exact keyword matches.
- **Metadata Filtering**: Filter results by fields such as genre, rating, and publication year.
- **Combined Search**: Combine semantic matching with exact filters to narrow down results.

## Project Structure

- `main.py`: The entry point script that initializes the database, populates it with sample book data, and runs example queries.
- `tools.py`: Contains helper functions for interacting with ChromaDB (creating clients, adding records, querying).
