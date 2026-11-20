from aiogram import BaseMiddleware
from aiogram.types import Message

from db.repositories.models import User
from telegram_bot import phrases


class RegisterUser(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        sender = event.from_user
        if sender:
            query = event.text
            excluded = ("/help", "/get_users", "/query", "/user_query", "/about", "/getcoms")
            if query and (query.startswith(excluded) or query in (phrases.FIND, data["settings"].admin_password)):
                query = None
            await data["users"].register(User(sender.id, sender.username, sender.first_name, sender.last_name), query)
        return await handler(event, data)
