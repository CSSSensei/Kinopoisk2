from aiogram.filters import BaseFilter
from aiogram.types import Message
import re

from DB.users_sqlite import Database


class CheckId(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(re.match(r'^/id_(\d+)$', message.text))


class AdminFilter(BaseFilter):
    def __init__(self, db: Database):
        self.db = db

    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        user = self.db.get_user(message.from_user.id)
        return bool(user.is_admin) if user else False

