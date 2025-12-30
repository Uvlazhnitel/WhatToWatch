from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class LLMExplanationItem(BaseModel):
    tmdb_id: int
    # 1–2 коротких предложения “почему это тебе”
    explanation: str = Field(min_length=1, max_length=280)
    # 2–4 коротких тега (для UI)
    tags: list[str] = Field(default_factory=list, max_length=6)


class LLMExplanationsOut(BaseModel):
    items: list[LLMExplanationItem]


class LLMQuestionsOut(BaseModel):
    questions: list[str] = Field(default_factory=list, max_length=2)


class LLMSummaryOut(BaseModel):
    summary_text: str = Field(min_length=1, max_length=520)
