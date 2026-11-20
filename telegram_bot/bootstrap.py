from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from db.repositories.media import MediaRepository
from db.repositories.telegram import TelegramRepository
from telegram_bot.config import BotConfig
from telegram_bot.container import build_container
from telegram_bot.handlers import admin_handlers, cards, commands, inline_handler, search
from telegram_bot.middlewares.users import RegisterUser


def build_dispatcher(
    settings: BotConfig, catalog: MediaRepository, users: TelegramRepository
) -> Dispatcher:
    dispatcher = Dispatcher(settings=settings, catalog=catalog, users=users)
    dispatcher.message.outer_middleware(RegisterUser())
    dispatcher.include_routers(
        admin_handlers.router(settings),
        commands.router(),
        cards.router(),
        inline_handler.router(),
        search.router(),
    )
    return dispatcher


async def run_bot() -> None:
    settings = BotConfig.load()
    async with AsyncExitStack() as stack:
        container = build_container(settings)
        stack.push_async_callback(container.close)
        bot = Bot(settings.token, session=AiohttpSession(proxy=settings.proxy_url))
        stack.push_async_callback(bot.session.close)
        dispatcher = build_dispatcher(
            settings, await container.get(MediaRepository), await container.get(TelegramRepository)
        )
        await dispatcher.start_polling(bot, close_bot_session=False)
