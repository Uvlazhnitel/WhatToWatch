from __future__ import annotations

from app.core.config import settings
from app.integrations.openai_text import llm_parse
from app.llm.schemas import LLMExplanationsOut, LLMQuestionsOut, LLMSummaryOut


SYSTEM = (
    "Ты — текстовый слой кино-агента.\n"
    "ВАЖНО:\n"
    "- Ты НЕ выбираешь фильмы и НЕ оцениваешь кандидатов.\n"
    "- Ты только формулируешь объяснения и вопросы на основе данных.\n"
    "- Не упоминай анти-темы/avoid'ы, если тебя прямо не попросили.\n"
    "- Пиши по-русски, коротко и естественно.\n"
)


def generate_explanations(payload: dict) -> LLMExplanationsOut:
    """
    payload: {
      "taste_summary": str,
      "items": [
        {"tmdb_id":int,"title":str,"year":int|None,"genres":[str], "keywords":[str],
         "sim_like":float,"novelty":float,"strategy":str}
      ]
    }
    """
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                "Сгенерируй объяснения для рекомендаций.\n"
                "Требования:\n"
                "- 1–2 предложения на фильм\n"
                "- никаких технических терминов (cosine, sim, penalty)\n"
                "- опирайся на taste_summary и метаданные фильма\n"
                "- можно добавить 2–4 тега (короткие)\n"
                "Верни строго по схеме.\n\n"
                f"ДАННЫЕ:\n{payload}"
            ),
        },
    ]
    return llm_parse(
        model=settings.openai_text_model,
        messages=messages,
        out_schema=LLMExplanationsOut,
        temperature=settings.openai_text_temperature,
        max_output_tokens=500,
    )


def generate_evening_questions(payload: dict) -> LLMQuestionsOut:
    """
    payload: {"taste_summary": str, "signal": str}
    signal — короткое описание почему мы спрашиваем (мало данных/хочется уточнить настроение).
    """
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                "Сформулируй 1–2 вечерних вопроса, чтобы лучше подобрать фильм.\n"
                "Требования:\n"
                "- вопросы должны быть простые (настроение/темп/жанр/страна/длина)\n"
                "- НЕ перечисляй много вариантов\n"
                "- максимум 2 вопроса\n"
                "Верни строго по схеме.\n\n"
                f"ДАННЫЕ:\n{payload}"
            ),
        },
    ]
    return llm_parse(
        model=settings.openai_text_model,
        messages=messages,
        out_schema=LLMQuestionsOut,
        temperature=0.45,
        max_output_tokens=220,
    )


def rewrite_profile_summary(payload: dict) -> LLMSummaryOut:
    """
    payload: {"weights_json": dict, "current_summary": str|None}
    """
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                "Сделай краткий, человеческий summary профиля вкуса.\n"
                "Требования:\n"
                "- 3–6 коротких строк, можно с буллетами\n"
                "- без воды, без 'как ИИ'\n"
                "- не придумывай факты: только из weights_json\n"
                "Верни строго по схеме.\n\n"
                f"ДАННЫЕ:\n{payload}"
            ),
        },
    ]
    return llm_parse(
        model=settings.openai_text_model,
        messages=messages,
        out_schema=LLMSummaryOut,
        temperature=0.25,
        max_output_tokens=260,
    )
