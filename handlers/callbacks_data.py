from aiogram.filters.callback_data import CallbackData


class MovieCallBack(CallbackData, prefix="movie"):
    movie_id: int
    action: int


class FactsCallBack(CallbackData, prefix="fact"):
    movie_id: int
    page: int
    action: int = 0


class CutMessageCallBack(CallbackData, prefix="cut"):
    action: int
    user_id: int = 0
    page: int = 1
