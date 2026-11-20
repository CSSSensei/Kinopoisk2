from uuid import uuid4

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from aiogram_dialog import DialogManager

from db.repositories.media import MediaRepository
from telegram_bot.dialogs.cards import MovieCard
from telegram_bot.keyboards.user_keyboards import keyboard
from telegram_bot.lexicon import phrase
from telegram_bot.presenters import web_url


async def send_card(message, card, dialog_manager):
    if card is None:
        await message.answer(phrase("catalog.missing"), reply_markup=keyboard)
        return
    poster = web_url(card.posterurl) or web_url(card.posterurlpreview)
    # Each card keeps its own message and navigation when another film is opened.
    async with dialog_manager.bg(stack_id=uuid4().hex).fg() as manager:
        manager.middleware_data["opening_card"] = card
        try:
            await manager.start(MovieCard.view, data={"media_id": card.media_id, "poster": poster})
        except TelegramBadRequest as exc:
            if not poster or not any(word in exc.message.lower() for word in ("photo", "url", "http", "file", "content type", "image")):
                raise
            manager.dialog_data["text_only"] = True
            await manager.show()


async def by_id(message: Message, catalog: MediaRepository, dialog_manager: DialogManager):
    await send_card(message, await catalog.card(int(message.text[4:].split("@")[0])), dialog_manager)


def router():
    result = Router(name="cards")
    result.message.register(by_id, F.text.regexp(r"^/id_\d{1,10}(?:@\w+)?$"))
    return result
