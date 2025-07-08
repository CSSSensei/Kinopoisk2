from typing import List
from aiogram import Router, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from config_data.models import Movie
from filters.UCommands import get_link
from DB.movie_interface import AbstractMovieDB
from config_data.config import Config, load_config
from DB.db_factory import DBFactory

config: Config = load_config()
db_instance: AbstractMovieDB = DBFactory.get_db_instance(config)

router = Router()


@router.inline_query()
async def inline_get_photo(query: types.InlineQuery):
    text = query.query
    movies_list: List[Movie] = db_instance.search_en_name(text)
    movies_result = []
    for id, movie in enumerate(movies_list):
        # movies_result.append(InlineQueryResultPhoto(id=str(id),thumbnail_url=f'https://st.kp.yandex.net/images/film_big/{movie.id}.jpg', photo_url=f'https://st.kp.yandex.net/images/film_big/{movie.id}.jpg', title=movie.ru_name or movie.en_name or 'Без названия', caption=movie.shortDescription))
        movies_result.append(InlineQueryResultArticle(id=str(id),
                                                      title=f'{movie.ru_name or movie.en_name or movie.alternativeName or "Без названия"} | {movie.year}',
                                                      thumbnail_url=get_link(movie.id), url=f'https://www.kinopoisk.ru/film/{movie.id}',
                                                      input_message_content=InputTextMessageContent(message_text=db_instance.get_info(movie)[6]),
                                                      hide_url=True,
                                                      description=f"{movie.rating_kp if movie.rating_kp else '–'} | {movie.shortDescription or movie.description or 'Без описания'}"))
    await query.answer(movies_result, cache_time=1, is_personal=True)
