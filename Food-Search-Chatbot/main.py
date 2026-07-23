import numpy as np
from sentence_transformers import SentenceTransformer
from tools import compute_cosine_similarity, euclidean_distance, dot_product

def main():
    documents = [
        'Bugs introduced by the intern had to be squashed by the lead developer.',
        'Bugs found by the quality assurance engineer were difficult to debug.',
        'Bugs are common throughout the warm summer months, according to the entomologist.',
        'Bugs, in particular spiders, are extensively studied by arachnologists.'
    ]
    
    print("Loading model...")
    model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
    
    print("Generating embeddings...")
    embeddings = model.encode(documents)
    
    print("\nCalculating metrics between Document 0 and Document 1:")
    print(f"Euclidean Distance: {euclidean_distance(embeddings[0], embeddings[1]):.4f}")
    print(f"Dot Product: {dot_product(embeddings[0], embeddings[1]):.4f}")
    
    print("\nComputing Cosine Similarity Matrix for all documents:")
    cosine_sim_matrix = compute_cosine_similarity(embeddings)
    print(np.round(cosine_sim_matrix, 4))

if __name__ == '__main__':
    main()
