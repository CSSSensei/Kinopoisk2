from aiogram.fsm.state import StatesGroup, State


class SearchMovie(StatesGroup):
    insert_film_name = State()  # Состояние ожидания ввода названия фильма
