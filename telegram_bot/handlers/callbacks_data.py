from typing import Literal

from aiogram.filters.callback_data import CallbackData

from telegram_bot.presenters import Section


class CardPage(CallbackData, prefix="card"):
    movie_id: int
    section: Section
    page: int = 0


class AdminPage(CallbackData, prefix="admin"):
    view: Literal["users", "queries"]
    user_id: int = 0
    page: int = 1
    part: int = 0
