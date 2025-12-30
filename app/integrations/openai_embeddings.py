"""
OpenAI Embeddings Integration

Wrapper for OpenAI's embeddings API with batching support.
Generates vector embeddings for text using OpenAI's text-embedding models.

Features:
- Batch processing for efficiency
- Configurable model and dimensions
- Error handling for empty/invalid inputs
- Returns embeddings in the same order as input texts

Used by the embedding_worker to generate semantic vectors for:
- Movie metadata
- User reviews
- Taste profiles
"""

from __future__ import annotations

from openai import OpenAI

from app.core.config import settings


_client = OpenAI(
    api_key=settings.openai_api_key,
    timeout=float(settings.openai_timeout_secs),
)


def embed_texts(texts: list[str], model: str | None = None, dimensions: int | None = None) -> list[list[float]]:
    """
    Возвращает embeddings в том же порядке, что и вход.
    Важно: input не может быть пустой строкой. :contentReference[oaicite:6]{index=6}
    """
    m = model or settings.openai_embed_model
    d = int(dimensions or settings.openai_embed_dimensions)

    cleaned: list[str] = []
    for t in texts:
        tt = (t or "").strip()
        if not tt:
            # нельзя эмбеддить пустоту — это лучше ловить заранее
            cleaned.append(" ")  # безопасный костыль, но лучше не допускать
        else:
            cleaned.append(tt)

    resp = _client.embeddings.create(
        model=m,
        input=cleaned,
        dimensions=d,  # поддерживается для text-embedding-3+ :contentReference[oaicite:7]{index=7}
    )
    return [row.embedding for row in resp.data]
