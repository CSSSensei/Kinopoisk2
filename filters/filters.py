from aiogram.filters import BaseFilter
from aiogram.types import Message
import re


class CheckId(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(re.match(r'^/id_(\d+)$', message.text))
