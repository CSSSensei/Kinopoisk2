import asyncio
from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.media import MediaRepository
from db.repositories.telegram import TelegramRepository
from telegram_bot.config import BotConfig
from telegram_bot.container import build_container
from telegram_bot.handlers import admin_handlers, cards, commands, inline_handler, search
from telegram_bot.middlewares.users import RegisterUser


def build_dispatcher(settings, catalog, users):
    dp = Dispatcher(settings=settings, catalog=catalog, users=users)
    dp.message.outer_middleware(RegisterUser())
    dp.include_routers(admin_handlers.router(settings), commands.router(), cards.router(),
                       inline_handler.router(), search.router())
    return dp


async def main():
    settings = BotConfig.load()
    async with AsyncExitStack() as stack:
        container = build_container(settings)
        stack.push_async_callback(container.close)
        engine = await container.get(AsyncEngine)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT m.top250 FROM kinopoisk.media m, kinopoisk.bot_credit_names, telegram.queries LIMIT 0"))
        bot = Bot(settings.token)
        stack.push_async_callback(bot.session.close)
        dp = build_dispatcher(settings, await container.get(MediaRepository), await container.get(TelegramRepository))
        await dp.start_polling(bot, close_bot_session=False)


if __name__ == "__main__":
    asyncio.run(main())
