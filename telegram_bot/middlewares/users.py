from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message

from db.repositories.models import User
from telegram_bot import phrases
from telegram_bot.handlers.admin_commands import ADMIN_NAMES

SKIP_HISTORY = ADMIN_NAMES | {"help", "about"}


def query_text(event, password):
    if isinstance(event, InlineQuery):
        return f"[INLINE] {event.query}" if event.query and event.query != password else None
    if not isinstance(event, Message) or not event.text or event.text in (password, phrases.FIND):
        return None
    if event.text.startswith("/"):
        command = event.text.split(maxsplit=1)[0][1:].partition("@")[0].lower()
        if command in SKIP_HISTORY:
            return None
    return event.text


class RegisterUser(BaseMiddleware):
    async def __call__(self, handler, event: Message | CallbackQuery | InlineQuery, data):
        sender = event.from_user
        if not sender:
            return await handler(event, data)
        banned = await data["users"].register(
            User(sender.id, sender.username, sender.first_name, sender.last_name),
            query_text(event, data["settings"].admin_password),
        )
        if banned:
            if isinstance(event, CallbackQuery):
                await event.answer()
            elif isinstance(event, InlineQuery):
                await event.answer([], cache_time=0, is_personal=True)
            return
        return await handler(event, data)
