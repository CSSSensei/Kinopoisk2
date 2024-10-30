import asyncio
from aiogram import Bot, Dispatcher

from DB.movie_DB import random_film
from config_data.config import Config, load_config
from handlers import user_handlers, admin_handlers, commands, callbacks, inline_handler


async def main() -> None:
    config: Config = load_config()

    bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
    dp = Dispatcher()
    dp.include_router(commands.router)
    dp.include_router(user_handlers.router)
    dp.include_router(callbacks.router)
    dp.include_router(inline_handler.router)
    print("Мувик запущен!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
