import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from db.repositories.media import MediaRepository
from telegram_bot import phrases
from telegram_bot.handlers.callbacks_data import FactsCallBack, MovieCallBack, SectionPage
from telegram_bot.keyboards.user_keyboards import keyboard, movie_keyboard
from telegram_bot.presenters import Section, pages, sections, web_url


async def send_card(message, card):
    if card is None:
        await message.answer(phrases.MISSING, reply_markup=keyboard)
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


async def show(callback, catalog, media_id, action, page=0):
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(phrases.STALE)
        return
    card = await catalog.card(media_id)
    if not card:
        await callback.answer(phrases.MISSING)
        return
    content = sections(card)
    if action not in content:
        await callback.answer("Этот раздел пуст.")
        return
    photo = bool(message.photo)
    chunks = pages(content[action], 1024 if photo else 4096)
    if not 0 <= page < len(chunks):
        await callback.answer(phrases.STALE)
        return
    markup = movie_keyboard(media_id, content, action, page, len(chunks))
    edit = message.edit_caption if photo else message.edit_text
    try:
        await edit(**chunks[page].kwargs(photo), reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
    await callback.answer()


async def movie(callback: CallbackQuery, callback_data: MovieCallBack, catalog: MediaRepository):
    await show(callback, catalog, callback_data.movie_id, callback_data.action)


async def section_page(callback: CallbackQuery, callback_data: SectionPage, catalog: MediaRepository):
    await show(callback, catalog, callback_data.movie_id, callback_data.action, callback_data.page)


async def facts(callback: CallbackQuery, callback_data: FactsCallBack, catalog: MediaRepository):
    if callback_data.action == -2:
        await callback.answer(str(callback_data.page + 1))
    else:
        await show(callback, catalog, callback_data.movie_id, Section.FACTS, callback_data.page)


LEGACY_ACTIONS = {"button_00_pressed": Section.CARD, "button_0_pressed": Section.DETAILS,
                  "big_button_1_pressed": Section.DESCRIPTION, "big_button_2_pressed": Section.SIMILAR,
                  "big_button_3_pressed": Section.TRAILER, "big_button_4_pressed": Section.FACTS,
                  "big_button_5_pressed": Section.RELATED}


async def legacy(callback: CallbackQuery, catalog: MediaRepository):
    message = callback.message
    body = (message.caption or message.text or "") if isinstance(message, Message) else ""
    found = re.search(r"(?:/id_|id:\s*)(\d{1,10})\b", body)
    if found:
        await show(callback, catalog, int(found[1]), LEGACY_ACTIONS[callback.data])
    else:
        await callback.answer(phrases.STALE)


def router():
    result = Router(name="cards")
    result.message.register(by_id, F.text.regexp(r"^/id_\d{1,10}(?:@\w+)?$"))
    result.callback_query.register(movie, MovieCallBack.filter())
    result.callback_query.register(section_page, SectionPage.filter())
    result.callback_query.register(facts, FactsCallBack.filter())
    result.callback_query.register(legacy, F.data.in_(LEGACY_ACTIONS))
    return result
