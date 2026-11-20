import logging
from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramAPIError

from db.repositories.media import MediaRepository
from db.repositories.telegram import TelegramRepository
from telegram_bot.config import BotConfig
from telegram_bot.container import build_container
from telegram_bot.handlers import admin_handlers, cards, commands, inline_handler, search
from telegram_bot.middlewares.users import RegisterUser

logger = logging.getLogger(__name__)


def build_dispatcher(
    settings: BotConfig, catalog: MediaRepository, users: TelegramRepository
) -> Dispatcher:
    dispatcher = Dispatcher(settings=settings, catalog=catalog, users=users)
    for observer in (dispatcher.message, dispatcher.callback_query, dispatcher.inline_query):
        observer.outer_middleware(RegisterUser())
    dispatcher.include_routers(
        admin_handlers.router(settings),
        commands.router(),
        cards.router(),
        inline_handler.router(),
        search.router(),
    )
    return dispatcher


async def run_bot() -> None:
    logger.info("Загрузка настроек бота")
    settings = BotConfig.load()
    async with AsyncExitStack() as stack:
        logger.info("Создание контейнера зависимостей")
        container = build_container(settings)
        stack.push_async_callback(container.close)
        logger.info("Создание сессии Telegram %s", "через прокси" if settings.proxy_url else "напрямую")
        bot = Bot(settings.token, session=AiohttpSession(proxy=settings.proxy_url))
        stack.push_async_callback(bot.session.close)
        logger.info("Регистрация middleware и роутеров")
        dispatcher = build_dispatcher(
            settings, await container.get(MediaRepository), await container.get(TelegramRepository)
        )
        logger.info("Запрос профиля бота через getMe")
        try:
            profile = await bot.me()
        except TelegramAPIError as exc:
            logger.error("Сбой getMe (%s)", type(exc).__name__)
            raise
        logger.info("Запуск polling для %s — https://t.me/%s", profile.first_name, profile.username)
        await dispatcher.start_polling(bot, close_bot_session=False)
