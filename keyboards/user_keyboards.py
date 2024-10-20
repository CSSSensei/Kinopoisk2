from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from DB.movie_DB import Movie
from handlers.callbacks import MovieCallBack, FactsCallBack

find_movie: KeyboardButton = KeyboardButton(text='Найти фильм')
random_movie: KeyboardButton = KeyboardButton(text='Рандомный фильм')

keyboard: ReplyKeyboardMarkup = ReplyKeyboardMarkup(
    keyboard=[[find_movie], [random_movie]],
    resize_keyboard=True,
    one_time_keyboard=False)


def movie_keyboard(movie: Movie, back=False):
    array_buttons: list[list[InlineKeyboardButton]] = []
    button_list = []
    if back:
        array_buttons.append([InlineKeyboardButton(text='Назад', callback_data=MovieCallBack(action=-1, movie_id=movie.id).pack())])
    else:
        if movie.description:
            button_list.append(InlineKeyboardButton(text='Синопсис', callback_data=MovieCallBack(action=0, movie_id=movie.id).pack()))
        if movie.trailer:
            button_list.append(InlineKeyboardButton(text='Трейлер', callback_data=MovieCallBack(action=1, movie_id=movie.id).pack()))
        if movie.similarMovies:
            button_list.append(InlineKeyboardButton(text='Похожие фильмы', callback_data=MovieCallBack(action=2, movie_id=movie.id).pack()))
        if movie.sequelsAndPrequels:
            button_list.append(InlineKeyboardButton(text='Сиквелы и приквелы', callback_data=MovieCallBack(action=3, movie_id=movie.id).pack()))
        if movie.facts:
            button_list.append(InlineKeyboardButton(text='Факты', callback_data=FactsCallBack(movie_id=movie.id, page=0).pack()))
        if movie:
            button_list.append(InlineKeyboardButton(text='Больше информации', callback_data=MovieCallBack(action=4, movie_id=movie.id).pack()))

        cnt = 0
        for button in button_list:
            if cnt % 2 == 0:
                array_buttons.append([])
            array_buttons[cnt // 2].append(button)
            cnt += 1
    markup = InlineKeyboardMarkup(inline_keyboard=array_buttons)
    return markup


def facts_keyboard(movie_id: int, page: int, max_page: int):
    array_buttons: list[list[InlineKeyboardButton]] = [[]]
    if page > 0:
        array_buttons[0].append(
            InlineKeyboardButton(text='<', callback_data=FactsCallBack(page=page - 1, movie_id=movie_id).pack())
        )
    if max_page != 1:
        array_buttons[0].append(
            InlineKeyboardButton(text=str(page + 1), callback_data=FactsCallBack(page=page, action=-2, movie_id=movie_id).pack())
        )
    if page < max_page - 1:
        array_buttons[0].append(
            InlineKeyboardButton(text='>', callback_data=FactsCallBack(page=page + 1, movie_id=movie_id).pack())
        )
    array_buttons.append([InlineKeyboardButton(text='Назад', callback_data=MovieCallBack(action=-1, movie_id=movie_id).pack())])
    markup = InlineKeyboardMarkup(inline_keyboard=array_buttons)
    return markup
