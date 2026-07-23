from tools import (
    get_chroma_client,
    get_embedding_function,
    create_or_get_collection,
    add_books_to_collection,
    search_books
)

def main():
    client = get_chroma_client()
    ef = get_embedding_function()
    collection = create_or_get_collection(client, "book_collection", ef)

    books = [
        {
            "id": "book_1",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "genre": "Classic",
            "year": 1925,
            "rating": 4.1,
            "pages": 180,
            "description": "A tragic tale of wealth, love, and the American Dream in the Jazz Age",
            "themes": "wealth, corruption, American Dream, social class",
            "setting": "New York, 1920s"
        },
        {
            "id": "book_2",
            "title": "To Kill a Mockingbird",
            "author": "Harper Lee",
            "genre": "Classic",
            "year": 1960,
            "rating": 4.3,
            "pages": 376,
            "description": "A powerful story of racial injustice and moral growth in the American South",
            "themes": "racism, justice, moral courage, childhood innocence",
            "setting": "Alabama, 1930s"
        },
        {
            "id": "book_3",
            "title": "1984",
            "author": "George Orwell",
            "genre": "Dystopian",
            "year": 1949,
            "rating": 4.4,
            "pages": 328,
            "description": "A chilling vision of totalitarian control and surveillance society",
            "themes": "totalitarianism, surveillance, freedom, truth",
            "setting": "Oceania, dystopian future"
        },
        {
            "id": "book_4",
            "title": "Harry Potter and the Philosopher's Stone",
            "author": "J.K. Rowling",
            "genre": "Fantasy",
            "year": 1997,
            "rating": 4.5,
            "pages": 223,
            "description": "A young wizard discovers his magical heritage and begins his education at Hogwarts",
            "themes": "friendship, courage, good vs evil, coming of age",
            "setting": "England, magical world"
        },
        {
            "id": "book_5",
            "title": "The Lord of the Rings",
            "author": "J.R.R. Tolkien",
            "genre": "Fantasy",
            "year": 1954,
            "rating": 4.5,
            "pages": 1216,
            "description": "An epic fantasy quest to destroy a powerful ring and save Middle-earth",
            "themes": "heroism, friendship, good vs evil, power corruption",
            "setting": "Middle-earth, fantasy realm"
        }
    ]

    add_books_to_collection(collection, books)
    
    print("Performing semantic search for 'magical fantasy adventure with friendship and courage'...")
    results = search_books(collection, query_texts=["magical fantasy adventure with friendship and courage"])
    if results and 'documents' in results and results['documents']:
        for doc in results['documents'][0]:
            print(f"- {doc}")

    print("\nFiltering for highly-rated books (>= 4.3)...")
    results = search_books(collection, where_filter={"rating": {"$gte": 4.3}})
    if results and 'metadatas' in results and results['metadatas']:
        for meta in results['metadatas']:
            print(f"- {meta['title']} ({meta['rating']} stars)")

if __name__ == '__main__':
    main()
