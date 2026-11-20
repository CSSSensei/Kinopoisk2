import asyncio
from aiogram import Dispatcher

from db.repositories.users import UserRepository
from db.connection import close_database, initialize_database
from telegram_bot.bot import bot
from telegram_bot.middleware import setup_middlewares
from telegram_bot.handlers import user_handlers, admin_handlers, commands, callbacks, inline_handler


async def main() -> None:
    initialize_database()
    dp = Dispatcher()
    db = UserRepository()
    setup_middlewares(dp, db)
    dp.include_router(admin_handlers.router)
    dp.include_router(commands.router)
    dp.include_router(user_handlers.router)
    dp.include_router(callbacks.router)
    dp.include_router(inline_handler.router)
    print("Мувик запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        close_database()


if __name__ == '__main__':
    asyncio.run(main())
