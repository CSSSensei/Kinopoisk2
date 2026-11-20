import asyncio
import logging
import shutil
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message
from aiogram.utils.formatting import Italic, Text

from db.repositories.telegram import TelegramRepository
from telegram_bot.config import BotConfig
from telegram_bot.dialogs.admin import admin_page, mention, query_list
from telegram_bot.handlers.admin_commands import ADMIN_COMMANDS, command_menu
from telegram_bot.handlers.callbacks_data import AdminPage
from telegram_bot.presenters import pages

logger = logging.getLogger(__name__)
TEMP_DIR = Path(__file__).resolve().parents[2] / "temp" / "telegram_bot"
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)


async def authorized(event, users: TelegramRepository):
    return bool(event.from_user and await users.is_admin(event.from_user.id))


async def grant(message: Message, users: TelegramRepository):
    await users.set_admin(message.from_user.id, True)
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.warning("Не удалось удалить сообщение с паролем администратора")
    await message.answer("Теперь Вы администратор")
    await commands(message)


async def commands(message: Message):
    await message.answer(**command_menu(admin=True).as_kwargs())


async def number(message: Message, command: CommandObject, default=None):
    args = (command.args or "").split()
    if not args:
        if default is None:
            await message.answer("⚠️ Ты не передал аргумент команды")
        return default
    value = args[0]
    if value.isascii() and value.isdecimal() and len(value) <= 19 and int(value) < 2**63:
        return int(value)
    await message.answer("⚠️ Аргумент команды не число")
    return None


async def target_user(message, command, users):
    user_id = await number(message, command)
    if user_id is None:
        return None
    user = await users.get_user(user_id)
    if user is None:
        await message.answer(**Text("⚠️ Пользователя ", Italic(str(user_id)), " не существует").as_kwargs())
    return user


async def moderate(message: Message, command: CommandObject, users: TelegramRepository):
    user = await target_user(message, command, users)
    if user is None:
        return
    name = command.command.lower()
    user_id = user["user_id"]
    if name == "ban" and user_id == message.from_user.id:
        await message.answer("⚠️ Нельзя заблокировать самого себя")
        return
    if name in ("ban", "unban"):
        ban = name == "ban"
        await users.set_banned(user_id, ban)
        response = Text("Пользователь ", mention(user), " успешно ", "заблокирован" if ban else "разблокирован")
    else:
        promote = name == "promote"
        await users.set_admin(user_id, promote)
        response = Text("Уровень доступа пользователя ", mention(user), " повышен" if promote else " понижен")
    await message.answer(**response.as_kwargs())


async def recent(message: Message, command: CommandObject, users: TelegramRepository):
    amount = await number(message, command, default=5)
    if amount is None:
        return
    offset = 0
    while offset < amount:
        rows = await users.queries(offset, min(amount - offset, 25))
        if not rows:
            break
        for chunk in pages(query_list(rows), 4096):
            await message.answer(**chunk.kwargs(), link_preview_options=NO_PREVIEW)
        offset += len(rows)
    if not offset:
        await message.answer("Запросов не было")


async def show_page(message, users, cursor):
    result = await admin_page(users, cursor)
    if result is None:
        await message.answer("⚠️ Пользователь не отправлял запросы")
        return
    page, markup = result
    await message.bot.send_message(message.from_user.id, **page.kwargs(), reply_markup=markup,
                                   link_preview_options=NO_PREVIEW)


async def show_users(message: Message, users: TelegramRepository):
    await show_page(message, users, AdminPage(view="users"))


async def user_queries(message: Message, command: CommandObject, users: TelegramRepository):
    user = await target_user(message, command, users)
    if user is not None:
        await show_page(message, users, AdminPage(view="queries", user_id=user["user_id"]))


async def turn_page(callback: CallbackQuery, users: TelegramRepository, callback_data: AdminPage | None = None):
    if not await authorized(callback, users):
        await callback.answer("Доступ только для администратора.")
        return
    if callback_data is None:
        await callback.answer()
        return
    result = await admin_page(users, callback_data)
    if not result or not isinstance(callback.message, Message):
        await callback.answer("Страница недоступна.")
        return
    page, markup = result
    try:
        await callback.message.edit_text(**page.kwargs(), reply_markup=markup, link_preview_options=NO_PREVIEW)
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
    await callback.answer()


def clear_temp_files():
    if TEMP_DIR.parent.is_symlink() or TEMP_DIR.is_symlink():
        raise OSError("Каталог временных файлов является ссылкой")
    if TEMP_DIR.exists():
        for path in TEMP_DIR.iterdir():
            if path.is_symlink() or not path.is_dir():
                path.unlink(missing_ok=True)
            else:
                shutil.rmtree(path)


async def clear_temp(message: Message):
    try:
        await asyncio.to_thread(clear_temp_files)
    except OSError:
        logger.exception("Ошибка очистки временных файлов")
        await message.answer("⚠️ Ошибка со стороны удалятеля")
        return
    await message.answer("Временные файлы очищены")


async def test_command(message: Message):
    pass


def router(settings: BotConfig):
    result = Router(name="admin")
    if settings.admin_password:
        result.message.register(grant, F.text == settings.admin_password, F.from_user)
    handlers = {
        "users": show_users, "commands": commands, "ban": moderate, "unban": moderate,
        "promote": moderate, "demote": moderate, "query": recent, "clear_temp": clear_temp,
        "user_query": user_queries, "test": test_command,
    }
    for aliases in ADMIN_COMMANDS:
        result.message.register(handlers[aliases[0]], Command(*aliases, ignore_case=True), authorized)
    result.callback_query.register(turn_page, AdminPage.filter())
    result.callback_query.register(turn_page, F.data == "admin:noop")
    return result
