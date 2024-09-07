from aiogram.filters import BaseFilter
from aiogram.types import Message


class CheckId(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        for i in message.text[4:]:
            if i not in '0123456789':
                return False
        return message.text[1:4] == 'id_'
