import os
import torch
from sentence_transformers import SentenceTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Embedding service using device: {device}")

# Load the multilingual-e5-large-instruct model
# This model is specifically chosen for its multilingual capabilities and
# its performance with instruction-based embeddings (like 'query:').
try:
    model = SentenceTransformer('intfloat/multilingual-e5-large-instruct', device=device)
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"Error loading embedding model: {e}")
    # In a real application, you might want to log this error and exit
    # or implement a fallback mechanism. For now, we'll just print.
    model = None # Set model to None if loading fails

def get_query_embedding(text: str) -> list:
    """
    Generates an embedding vector for the given query text.

    Args:
        text (str): The input query text.

    Returns:
        list: A list representing the dense embedding vector.
              Returns an empty list if the model failed to load or input is empty.
    """
    if not model:
        print("Embedding model is not loaded. Cannot generate embedding.")
        return []
    
    if not text.strip():
        print("Input text for embedding is empty.")
        return []

    # Add the 'query:' prefix as recommended for the E5 instruct model
    # This helps the model understand that the input is a query.
    embedding = model.encode(f"query: {text}").tolist()
    return embedding


