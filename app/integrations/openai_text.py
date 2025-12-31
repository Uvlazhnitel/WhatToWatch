from __future__ import annotations

import logging
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import OpenAIError as CustomOpenAIError

logger = logging.getLogger(__name__)

_client = OpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout_secs,
    max_retries=3,
)


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
    Используем Responses API (современный интерфейс) с retry logic.
    
    Args:
        model: OpenAI model name
        messages: List of message dictionaries
        out_schema: Pydantic model for output validation
        temperature: Generation temperature (0-1)
        max_output_tokens: Maximum tokens to generate
        
    Returns:
        Parsed output matching out_schema
        
    Raises:
        CustomOpenAIError: If OpenAI API call fails
    """
    try:
        resp = _client.responses.parse(
            model=model,
            input=messages,
            temperature=temperature if temperature is not None else settings.openai_text_temperature,
            max_output_tokens=max_output_tokens if max_output_tokens is not None else settings.openai_text_max_output_tokens,
            text_format=out_schema,
            store=False,
        )
        return resp.output_parsed
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}", exc_info=True)
        raise CustomOpenAIError(
            f"OpenAI API error: {e}",
            user_message="Не удалось сгенерировать текст. Попробуйте позже."
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in OpenAI call: {e}", exc_info=True)
        raise CustomOpenAIError(
            f"Unexpected error: {e}",
            user_message="Произошла ошибка при генерации текста."
        ) from e
