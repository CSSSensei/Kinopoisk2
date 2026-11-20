from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.formatting import Text

from db.repositories.media import MediaRepository
from telegram_bot import phrases
from telegram_bot.handlers.cards import send_card
from telegram_bot.keyboards.user_keyboards import keyboard
from telegram_bot.presenters import pages, web_url
from telegram_bot.states.states import SearchMovie


async def begin(message: Message, state: FSMContext):
    await state.set_state(SearchMovie.insert_film_name)
    await message.answer("Введите название фильма", reply_markup=ReplyKeyboardRemove())


async def search(message: Message, state: FSMContext, catalog: MediaRepository):
    if not message.text:
        await message.answer("Введите название фильма текстом.")
        return
    matches = await catalog.search(message.text)
    if matches:
        poster = web_url(matches[0].posterurlpreview) or web_url(matches[0].posterurl)
        if poster:
            try:
                await message.answer_photo(poster)
            except TelegramBadRequest:
                pass
        entries = [f"{m.title} ({m.release_year or '—'}, рейтинг КП: {m.rating if m.rating is not None else '—'})"
                   f"   /id_{m.media_id}" for m in matches]
        for page in pages(Text("\n".join(entries)), 4096):
            await message.answer(**page.kwargs(), reply_markup=keyboard)
    else:
        await message.answer(phrases.NO_RESULTS, reply_markup=keyboard)
    await state.clear()


async def random_media(message: Message, catalog: MediaRepository):
    card = await catalog.random()
    if card:
        await send_card(message, card)
    else:
        await message.answer("Сейчас нет фильмов с подходящим рейтингом.", reply_markup=keyboard)


async def thanks(message: Message):
    await message.answer_sticker(phrases.THANKS_STICKER)


async def fallback(message: Message):
    await message.answer("К сожалению, я не понимаю, о чем вы", reply_markup=keyboard)


def router():
    result = Router(name="search")
    result.message.register(begin, F.text == phrases.FIND)
    result.message.register(search, StateFilter(SearchMovie.insert_film_name))
    result.message.register(random_media, F.text == phrases.RANDOM)
    result.message.register(thanks, F.text.lower().in_({"спасибо", "от души", "благодарю"}))
    result.message.register(fallback)
    return result
