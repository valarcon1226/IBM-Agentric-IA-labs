import chromadb
from chromadb.utils import embedding_functions

def get_chroma_client():
    """Returns a ChromaDB client."""
    return chromadb.Client()

def get_embedding_function():
    """Returns the sentence transformer embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

def create_or_get_collection(client, collection_name, embedding_function):
    """Creates or retrieves a ChromaDB collection."""
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "A collection for storing data"},
        embedding_function=embedding_function
    )

def add_books_to_collection(collection, books):
    """Formats book data and adds it to the specified collection."""
    book_documents = []
    for book in books:
        document = f"{book['title']} by {book['author']}. {book['description']} "
        document += f"Themes: {book['themes']}. Setting: {book['setting']}. "
        document += f"Genre: {book['genre']} published in {book['year']}."
        book_documents.append(document)

    collection.add(
        ids=[book["id"] for book in books],
        documents=book_documents,
        metadatas=[{
            "title": book["title"],
            "author": book["author"],
            "genre": book["genre"],
            "year": book["year"],
            "rating": book["rating"],
            "pages": book["pages"]
        } for book in books]
    )

def search_books(collection, query_texts=None, n_results=3, where_filter=None):
    """Performs a search on the book collection."""
    if query_texts and where_filter:
        return collection.query(query_texts=query_texts, n_results=n_results, where=where_filter)
    elif query_texts:
        return collection.query(query_texts=query_texts, n_results=n_results)
    elif where_filter:
        return collection.get(where=where_filter)
    else:
        return collection.get()
