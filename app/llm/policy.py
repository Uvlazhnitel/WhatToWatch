from __future__ import annotations

def should_ask_questions(
    *,
    rated_films_count: int,
    embeddings_coverage_ratio: float,
    avg_sim_like: float,
) -> tuple[bool, str]:
    """
    Решение делается детерминированно.
    LLM только формулирует текст.
    """
    if rated_films_count < 15:
        return True, "Мало оценённых фильмов — хочу уточнить предпочтения."
    if embeddings_coverage_ratio < 0.55:
        return True, "Пока не на все фильмы есть смысловые вектора — уточню настроение."
    if avg_sim_like < 0.18:
        return True, "Сигнал вкуса слабый — уточню, что хочется сегодня."
    return False, ""
