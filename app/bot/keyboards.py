from aiogram.utils.keyboard import InlineKeyboardBuilder


def movie_pick_keyboard(candidates: list[dict]) -> InlineKeyboardBuilder:
    """
    candidates: [{tmdb_id, title, year}, ...]
    """
    kb = InlineKeyboardBuilder()
    for c in candidates[:5]:
        title = c.get("title", "Unknown")
        year = c.get("year")
        text = f"{title} ({year})" if year else title
        kb.button(text=text[:64], callback_data=f"pick:{c['tmdb_id']}")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb


def rec_item_keyboard(item_id: int, tmdb_id: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Посмотрел", callback_data=f"watched:{item_id}:{tmdb_id}")
    kb.button(text="⏭ Пропустить", callback_data=f"skip:{item_id}")
    kb.adjust(2)
    return kb
