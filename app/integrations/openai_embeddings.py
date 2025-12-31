from __future__ import annotations

import logging
from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

_client = OpenAI(
    api_key=settings.openai_api_key,
    timeout=float(settings.openai_timeout_secs),
    max_retries=3,
)


def embed_texts(texts: list[str], model: str | None = None, dimensions: int | None = None) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
        model: OpenAI embedding model (defaults to settings)
        dimensions: Embedding dimensions (defaults to settings)
        
    Returns:
        List of embedding vectors in same order as input
        
    Raises:
        EmbeddingError: If embedding generation fails
        
    Note:
        Empty strings are replaced with a single space to avoid API errors.
    """
    m = model or settings.openai_embed_model
    d = int(dimensions or settings.openai_embed_dimensions)

    cleaned: list[str] = []
    for t in texts:
        tt = (t or "").strip()
        if not tt:
            # OpenAI API doesn't accept empty strings
            cleaned.append(" ")
            logger.warning("Empty text provided for embedding, using space instead")
        else:
            cleaned.append(tt)

    try:
        resp = _client.embeddings.create(
            model=m,
            input=cleaned,
            dimensions=d,
        )
        return [row.embedding for row in resp.data]
    except OpenAIError as e:
        logger.error(f"OpenAI embedding error: {e}", exc_info=True)
        raise EmbeddingError(
            f"Failed to generate embeddings: {e}",
            user_message="Не удалось создать эмбеддинги. Попробуйте позже."
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error generating embeddings: {e}", exc_info=True)
        raise EmbeddingError(
            f"Unexpected embedding error: {e}",
            user_message="Произошла ошибка при создании эмбеддингов."
        ) from e
