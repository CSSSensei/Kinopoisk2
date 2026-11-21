from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.formatting import Text

from aiogram_dialog import DialogManager

from db.repositories.media import MediaRepository
from telegram_bot.lexicon import phrase
from telegram_bot.handlers.cards import send_card
from telegram_bot.keyboards.user_keyboards import keyboard
from telegram_bot.presenters import pages, poster_url
from telegram_bot.states.states import SearchMovie


async def begin(message: Message, state: FSMContext):
    await state.set_state(SearchMovie.insert_film_name)
    await message.answer(phrase("search.prompt"), reply_markup=ReplyKeyboardRemove())


async def search(message: Message, state: FSMContext, catalog: MediaRepository):
    if not message.text:
        await message.answer(phrase("search.text_only"))
        return
    matches = await catalog.search(message.text)
    if matches:
        try:
            await message.answer_photo(poster_url(matches[0], preview=True))
        except TelegramBadRequest:
            pass
        entries = [phrase("search.result").format(title=m.title, year=m.release_year or "—",
                                                   rating=m.rating if m.rating is not None else "—", media_id=m.media_id) for m in matches]
        for page in pages(Text("\n".join(entries)), 4096):
            await message.answer(**page.kwargs(), reply_markup=keyboard)
    else:
        await message.answer(phrase("catalog.no_results"), reply_markup=keyboard)
    await state.clear()


async def random_media(message: Message, catalog: MediaRepository, dialog_manager: DialogManager):
    card = await catalog.random()
    if card:
        await send_card(message, card, dialog_manager)
    else:
        await message.answer(phrase("catalog.no_random"), reply_markup=keyboard)


async def thanks(message: Message):
    await message.answer_sticker(phrase("answers.thanks_sticker"))


async def fallback(message: Message):
    await message.answer(phrase("answers.unknown"), reply_markup=keyboard)


def router():
    result = Router(name="search")
    result.message.register(begin, F.text == phrase("buttons.find"))
    result.message.register(search, StateFilter(SearchMovie.insert_film_name))
    result.message.register(random_media, F.text == phrase("buttons.random"))
    result.message.register(thanks, F.text.lower().in_(phrase("answers.thanks_triggers").split("|")))
    result.message.register(fallback)
    return result
