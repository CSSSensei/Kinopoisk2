from dataclasses import dataclass

from aiogram.types import MessageEntity
from aiogram.utils.formatting import Text


@dataclass
class Page:
    text: str
    entities: list[MessageEntity]

    def kwargs(self, caption=False):
        if caption:
            return dict(caption=self.text, caption_entities=self.entities, parse_mode=None)
        return dict(text=self.text, entities=self.entities, parse_mode=None)


def pages(content: Text, limit: int) -> list[Page]:
    body, entities = content.render()
    result = []
    start = offset = 0
    while start < len(body):
        end = min(start + limit, len(body))
        # Telegram entity offsets and lengths count UTF-16 code units.
        size = len(body[start:end].encode("utf-16-le")) // 2
        while size > limit:
            end -= 1
            size -= 2 if ord(body[end]) > 0xffff else 1
        if end < len(body):
            boundary = body.rfind("\n", start, end)
            if boundary > start:
                end = boundary + 1
        chunk = body[start:end]
        next_offset = offset + len(chunk.encode("utf-16-le")) // 2
        clipped = []
        for ent in entities:
            left, right = max(offset, ent.offset), min(next_offset, ent.offset + ent.length)
            if right > left:
                clipped.append(ent.model_copy(update={"offset": left - offset, "length": right - left}))
        result.append(Page(chunk, clipped))
        start, offset = end, next_offset
    return result
