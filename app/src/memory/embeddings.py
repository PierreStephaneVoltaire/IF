"""Centralized embedding utility for LanceDB storage.

Provides a singleton embedding model that can be shared across
all LanceDB table operations.
"""
from __future__ import annotations
import os
import logging
from functools import lru_cache
from typing import List, Optional

from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# Track if we've logged model load
_model_load_logged = False


@lru_cache(maxsize=1)
def get_embedding_model():
    """Get the sentence transformer model (cached).

    Returns:
        SentenceTransformer model instance

    Raises:
        ImportError: If sentence-transformers is not installed
    """
    global _model_load_logged

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required for embeddings. "
            "Install with: pip install sentence-transformers"
        )

    model = SentenceTransformer(EMBEDDING_MODEL)

    if not _model_load_logged:
        logger.info(f"Loaded embedding model: {EMBEDDING_MODEL} (dimension: {EMBEDDING_DIMENSION})")
        _model_load_logged = True

    return model


def embed(text: str) -> List[float]:
    """Generate embedding vector for a text string.

    Args:
        text: The text to embed

    Returns:
        List of floats representing the embedding vector
    """
    if not text or not text.strip():
        # Return zero vector for empty text
        return [0.0] * EMBEDDING_DIMENSION

    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embedding vectors for multiple texts.

    More efficient than calling embed() multiple times.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    model = get_embedding_model()

    # Handle empty strings
    processed = [t if t and t.strip() else " " for t in texts]

    embeddings = model.encode(processed)
    return [e.tolist() for e in embeddings]


def get_embedding_dimension() -> int:
    """Get the embedding dimension for the current model.

    Returns:
        The dimension of embedding vectors
    """
    return EMBEDDING_DIMENSION
