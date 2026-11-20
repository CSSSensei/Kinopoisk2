from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from aiogram.types import MessageEntity
from aiogram.utils.formatting import Bold, Spoiler, Text, TextLink

from db.repositories.media import MediaCard, MediaSummary


class Section(StrEnum):
    CARD = "card"
    DESCRIPTION = "description"
    TRAILER = "trailer"
    SIMILAR = "similar"
    RELATED = "related"
    DETAILS = "details"
    FACTS = "facts"


LABELS = {
    Section.DESCRIPTION: "Синопсис", Section.TRAILER: "Трейлер",
    Section.SIMILAR: "Похожие фильмы", Section.RELATED: "Связанные фильмы",
    Section.DETAILS: "Больше информации", Section.FACTS: "Факты",
}


def web_url(value) -> str | None:
    if isinstance(value, str):
        try:
            url = urlsplit(value)
            if url.scheme in {"http", "https"} and url.hostname:
                return value
        except ValueError:
            pass
    return None


def trailer_links(value):
    if isinstance(value, list):
        for entry in value:
            yield from trailer_links(entry)
    elif isinstance(value, dict):
        yield from trailer_links(value.get("url") or value.get("trailers"))
    elif url := web_url(value):
        yield url


def money(value):
    if isinstance(value, dict):
        amount = value.get("amount", value.get("value"))
        currency = value.get("currency_symbol") or value.get("currency_code") or value.get("currency") or ""
        return f"{amount} {currency}".strip() if amount is not None else None
    return value


def summary(m: MediaSummary):
    heading = Text(TextLink(m.title, url=f"https://www.kinopoisk.ru/film/{m.media_id}/"), f" (/id_{m.media_id})")
    return lines(heading, [("Рейтинг", m.rating), ("Год", m.release_year), ("Жанры", ", ".join(m.genres)),
                           ("Страна", ", ".join(m.countries)), ("Режиссёр", ", ".join(m.directors))])


def lines(heading, fields):
    return Text(heading, *(Text("\n", Bold(label + ": "), value) for label, value in fields
                           if value is not None and value != ""))


def sections(m: MediaCard) -> dict[Section, Text]:
    card = summary(m)
    result = {Section.CARD: card, Section.DETAILS: lines(card, [
        ("Количество оценок", m.votes), ("Тип", m.type), ("Длительность, мин", m.duration),
        ("Возраст", m.age_rating), ("MPAA", m.rating_mpaa), ("Бюджет", money(m.budget_value)),
        ("Мировые сборы", money(m.fees_world)), ("Место в топ-250", m.top250),
        ("Актёры", ", ".join(m.actors))])}
    description = "\n\n".join(dict.fromkeys(x for x in (m.description, m.short_description) if x))
    if description:
        result[Section.DESCRIPTION] = Text(description)
    trailers = list(dict.fromkeys(trailer_links(m.trailer)))
    if trailers:
        result[Section.TRAILER] = Text("\n".join(trailers))
    if m.facts:
        result[Section.FACTS] = Text(*(Text("\n\n" if i else "", Spoiler(f["body"]) if f["is_spoiler"] else f["body"])
                                       for i, f in enumerate(m.facts)))
    for section, related in ((Section.SIMILAR, m.similar), (Section.RELATED, m.relations)):
        entries = [f"{r['title']} (/id_{r['id']})" + (f" — {r['kind']}" if "kind" in r else "") for r in related]
        if entries:
            result[section] = Text(Bold(LABELS[section]), "\n", "\n".join(entries))
    return result


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
