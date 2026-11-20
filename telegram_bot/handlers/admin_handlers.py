from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Text

from db.repositories.telegram import TelegramRepository
from telegram_bot import phrases
from telegram_bot.config import BotConfig
from telegram_bot.dialogs.admin import admin_page, query_line
from telegram_bot.handlers.callbacks_data import CutMessageCallBack, HistoryChunk
from telegram_bot.presenters import pages


async def authorized(event, users: TelegramRepository):
    return bool(event.from_user and await users.is_admin(event.from_user.id))


async def grant(message: Message, users: TelegramRepository):
    await users.set_admin(message.from_user.id, True)
    await message.answer("Теперь ты админ")


async def commands(message: Message):
    await message.answer("/get_users\n/query [число] — последние запросы\n/user_query <ID> — история пользователя\n/help\n/about")


def number(command):
    raw = (command.args or "").strip()
    return int(raw) if raw.isascii() and raw.isdecimal() and len(raw) <= 19 and int(raw) < 2**63 else None


async def recent(message: Message, command: CommandObject, users: TelegramRepository):
    amount = number(command) if command.args else 5
    if amount is None:
        await message.answer("Используйте /query <число>")
        return
    offset = 0
    while offset < amount:
        rows = await users.queries(offset, min(amount-offset, 50))
        if not rows:
            break
        for page in pages(Text("\n\n".join(map(query_line, rows))), 4096):
            await message.answer(**page.kwargs())
        offset += len(rows)
    if not offset:
        await message.answer("Запросов не было")


async def open_page(message: Message, command: CommandObject, users: TelegramRepository):
    history = command.command.lower() == "user_query"
    target = number(command) if history else 0
    result = await admin_page(users, 2 if history else 1, target, 1) if target is not None else None
    if result:
        page, markup = result
        await message.bot.send_message(message.from_user.id, **page.kwargs(), reply_markup=markup)
    else:
        await message.answer("Укажите ID пользователя с историей запросов.")


async def turn_page(callback: CallbackQuery, callback_data: CutMessageCallBack | HistoryChunk, users: TelegramRepository):
    if not await authorized(callback, users):
        await callback.answer("Доступ только для администратора.")
        return
    if isinstance(callback_data, HistoryChunk):
        action, chunk = 2, callback_data.chunk
    else:
        action, chunk = callback_data.action, 0
    if action == -1:
        await callback.answer()
        return
    result = await admin_page(users, action, callback_data.user_id, callback_data.page, chunk)
    if not result or not isinstance(callback.message, Message):
        await callback.answer(phrases.STALE)
        return
    page, markup = result
    try:
        await callback.message.edit_text(**page.kwargs(), reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
    await callback.answer()


def router(settings: BotConfig):
    result = Router(name="admin")
    if settings.admin_password:
        result.message.register(grant, F.text == settings.admin_password, F.from_user)
    result.message.register(commands, Command("getcoms"), authorized)
    result.message.register(recent, Command("query"), authorized)
    result.message.register(open_page, Command("get_users", "user_query"), authorized)
    result.callback_query.register(turn_page, CutMessageCallBack.filter())
    result.callback_query.register(turn_page, HistoryChunk.filter())
    return result
