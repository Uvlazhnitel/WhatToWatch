from __future__ import annotations

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings


_client = OpenAI(api_key=settings.openai_api_key)


def llm_parse(
    *,
    model: str,
    messages: list[dict],
    out_schema: type[BaseModel],
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> BaseModel:
    """
    Structured Outputs: гарантируем JSON по схеме.
    Используем Responses API (современный интерфейс). :contentReference[oaicite:4]{index=4}
    """
    resp = _client.responses.parse(
        model=model,
        input=messages,
        temperature=temperature if temperature is not None else settings.openai_text_temperature,
        max_output_tokens=max_output_tokens if max_output_tokens is not None else settings.openai_text_max_output_tokens,
        text_format=out_schema,
        store=False,
    )
    return resp.output_parsed
