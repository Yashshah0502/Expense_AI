import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

# Global singleton for the embedding model
# This ensures we only load the heavy model once per process.
_embed_model = None

def get_embedding_model():
    """Returns the lazy-loaded global embedding model."""
    global _embed_model
    if _embed_model is None:
        # BAAI/bge-m3 output dimension is 1024
        _embed_model = SentenceTransformer("BAAI/bge-m3")
    return _embed_model

def get_embedding(text: str) -> list[float]:
    """Generates a normalized embedding for a single string."""
    model = get_embedding_model()
    # normalize_embeddings=True for cosine similarity
    return model.encode([text], normalize_embeddings=True)[0].tolist()

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generates normalized embeddings for a list of strings."""
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]
