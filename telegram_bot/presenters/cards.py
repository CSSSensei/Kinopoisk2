from enum import StrEnum

from aiogram.utils.formatting import Bold, Spoiler, Text, TextLink

from db.repositories.media import MediaCard, MediaSummary
from telegram_bot.presenters.links import trailer_links


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
