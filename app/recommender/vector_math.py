from __future__ import annotations

import math
from typing import Iterable


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity [-1..1]. Если один из векторов нулевой — 0.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def weighted_average(vectors_with_w: Iterable[tuple[list[float], float]]) -> list[float] | None:
    """
    Считает weighted average. Возвращает None, если нет ни одного вектора.
    """
    acc = None
    total_w = 0.0
    for vec, w in vectors_with_w:
        if not vec or w <= 0:
            continue
        if acc is None:
            acc = [0.0] * len(vec)
        for i, x in enumerate(vec):
            acc[i] += x * w
        total_w += w

    if acc is None or total_w <= 0:
        return None

    return [x / total_w for x in acc]
