from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message

from db.models import UserRecord
from telegram_bot.lexicon import phrase
from telegram_bot.handlers.admin_commands import ADMIN_NAMES

SKIP_HISTORY = ADMIN_NAMES | {"help", "about"}


def query_text(event, password):
    if isinstance(event, InlineQuery):
        return f"[INLINE] {event.query}" if event.query and event.query != password else None
    if not isinstance(event, Message) or not event.text or event.text in (password, phrase("buttons.find")):
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
        user = UserRecord(
            user_id=sender.id,
            username=sender.username,
            first_name=sender.first_name,
            last_name=sender.last_name,
        )
        banned = await data["users"].register(user, query=query_text(event, data["settings"].admin_password))
        if banned:
            if isinstance(event, CallbackQuery):
                await event.answer()
            elif isinstance(event, InlineQuery):
                await event.answer([], cache_time=0, is_personal=True)
            return
        return await handler(event, data)
