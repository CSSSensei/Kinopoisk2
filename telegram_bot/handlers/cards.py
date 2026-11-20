from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from db.repositories.media import MediaRepository
from telegram_bot.lexicon import phrase
from telegram_bot.handlers.callbacks_data import CardPage
from telegram_bot.keyboards.user_keyboards import keyboard, movie_keyboard
from telegram_bot.presenters import Section, pages, sections, web_url


async def send_card(message, card):
    if card is None:
        await message.answer(phrase("catalog.missing"), reply_markup=keyboard)
        return
    content = sections(card)
    poster = web_url(card.posterurl) or web_url(card.posterurlpreview)
    if poster:
        chunks = pages(content[Section.CARD], 1024)
        try:
            await message.answer_photo(poster, **chunks[0].kwargs(True),
                                       reply_markup=movie_keyboard(card.media_id, content, total=len(chunks)))
            return
        except TelegramBadRequest as exc:
            if not any(word in exc.message.lower() for word in ("photo", "url", "http", "file", "content type", "image")):
                raise
    chunks = pages(content[Section.CARD], 4096)
    await message.answer(**chunks[0].kwargs(), reply_markup=movie_keyboard(card.media_id, content, total=len(chunks)))


async def by_id(message: Message, catalog: MediaRepository):
    await send_card(message, await catalog.card(int(message.text[4:].split("@")[0])))


async def show(callback: CallbackQuery, callback_data: CardPage, catalog: MediaRepository):
    section, page = callback_data.section, callback_data.page
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(phrase("catalog.stale"))
        return
    card = await catalog.card(callback_data.movie_id)
    if not card:
        await callback.answer(phrase("catalog.missing"))
        return
    content = sections(card)
    if section not in content:
        await callback.answer(phrase("catalog.empty_section"))
        return
    photo = bool(message.photo)
    chunks = pages(content[section], 1024 if photo else 4096)
    if not 0 <= page < len(chunks):
        await callback.answer(phrase("catalog.stale"))
        return
    markup = movie_keyboard(card.media_id, content, section, page, len(chunks))
    edit = message.edit_caption if photo else message.edit_text
    try:
        await edit(**chunks[page].kwargs(photo), reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
    await callback.answer()


def router():
    result = Router(name="cards")
    result.message.register(by_id, F.text.regexp(r"^/id_\d{1,10}(?:@\w+)?$"))
    result.callback_query.register(show, CardPage.filter())
    return result
