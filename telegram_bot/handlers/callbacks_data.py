from aiogram.filters.callback_data import CallbackData

from telegram_bot.presenters import Section


class CardPage(CallbackData, prefix="card"):
    movie_id: int
    section: Section
    page: int = 0


class CutMessageCallBack(CallbackData, prefix="cut"):
    action: int
    user_id: int = 0
    page: int = 1


class HistoryChunk(CallbackData, prefix="history"):
    user_id: int
    page: int
    chunk: int
