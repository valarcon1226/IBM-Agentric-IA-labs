import math
import numpy as np

def euclidean_distance(vector1, vector2):
    """Calculate the Euclidean distance between two vectors."""
    squared_sum = sum((x - y) ** 2 for x, y in zip(vector1, vector2))
    return math.sqrt(squared_sum)

def dot_product(vector1, vector2):
    """Calculate the dot product of two vectors."""
    return sum(x * y for x, y in zip(vector1, vector2))

def compute_cosine_similarity(embeddings):
    """Compute cosine similarity matrix for a set of embeddings."""
    l2_norms = np.sqrt(np.sum(embeddings**2, axis=1)).reshape(-1, 1)
    normalized_embeddings = embeddings / l2_norms
    cosine_similarity_matrix = normalized_embeddings @ normalized_embeddings.T
    return cosine_similarity_matrix
