from aiogram import BaseMiddleware, Dispatcher
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import Message, TelegramObject

from DB.users_sqlite import Database
from config_data.models import User, Query


class UserRegistrationMiddleware(BaseMiddleware):
    def __init__(self, db: Database):
        self.db = db

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        skip_commands = ['/help', '/get_users', '/query', '/user_query', '/about', '/getcoms']

        if event.text and any(event.text.startswith(cmd) for cmd in skip_commands):
            return await handler(event, data)

        user = event.from_user

        if not user:
            return await handler(event, data)
        db_user = User(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        self.db.add_user(db_user)
        if event.text:
            if event.text == 'Найти фильм':
                return await handler(event, data)
            self.db.add_query(Query(user_id=event.from_user.id, query_text=event.text))

        return await handler(event, data)


def setup_middlewares(dp: Dispatcher, db: Database):
    # Создаем экземпляр middleware и передаем в него базу данных
    user_middleware = UserRegistrationMiddleware(db)

    # Регистрируем middleware для всех сообщений
    dp.message.middleware.register(user_middleware)
