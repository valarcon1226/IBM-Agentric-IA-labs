import chromadb
from chromadb.utils import embedding_functions

# Configurar el modelo para convertir texto a vectores
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Iniciar la base de datos Chroma
client = chromadb.Client()
collection_name = "my_grocery_collection"

def main():
    try:
        # Crear la colección
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "A collection for storing grocery data"},
            configuration={
                "hnsw": {"space": "cosine"},
                "embedding_function": ef
            }
        )
        print(f"Collection created: {collection.name}")

        # Datos del supermercado
        texts = [
            'fresh red apples', 'organic bananas', 'ripe mangoes',
            'whole wheat bread', 'farm-fresh eggs', 'natural yogurt',
            'frozen vegetables', 'grass-fed beef', 'free-range chicken',
            'fresh salmon fillet', 'aromatic coffee beans', 'pure honey',
            'golden apple', 'red fruit'
        ]

        # Crear IDs únicos como food_1, food_2...
        ids = [f"food_{index + 1}" for index, _ in enumerate(texts)]

        # Guardar en la base de datos
        collection.add(
            documents=texts,
            metadatas=[{"source": "grocery_store", "category": "food"} for _ in texts],
            ids=ids
        )

        all_items = collection.get()
        print("Collection contents:")
        print(f"Number of documents: {len(all_items['documents'])}")

        # Función para buscar
        def perform_similarity_search(collection, all_items):
            try:
                # Vamos a buscar "red" (rojo) y "fresh" (fresco)
                query_term = ["red", "fresh"]
                if isinstance(query_term, str):
                    query_term = [query_term]

                results = collection.query(
                    query_texts=query_term,
                    n_results=3  # Traer los 3 más parecidos
                )
                print(f"\nQuery results for '{query_term}':")

                if not results or not results['ids'] or len(results['ids'][0]) == 0:
                    print(f'No documents found similar to "{query_term}"')
                    return
                
                # Imprimir los resultados bonitos en pantalla
                for q in range(len(query_term)):
                    print(f'\nTop 3 similar documents to "{query_term[q]}":')
                    for i in range(min(3, len(results['ids'][q]))):
                        doc_id = results['ids'][q][i]
                        score = results['distances'][q][i]
                        text = results['documents'][q][i]
                        if not text:
                            print(f' - ID: {doc_id}, Text: "Text not available", Score: {score:.4f}')
                        else:
                            print(f' - ID: {doc_id}, Text: "{text}", Score: {score:.4f}')
            except Exception as error:
                print(f"Error in similarity search: {error}")
        
        perform_similarity_search(collection, all_items)
    except Exception as error:
        print(f"Error: {error}")

if __name__ == "__main__":
    main()
