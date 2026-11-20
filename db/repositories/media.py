from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from db.query_loader import load_query


@dataclass(frozen=True)
class MediaSummary:
    media_id: int
    title: str
    release_year: int | None
    rating: float | None
    posterurl: str | None
    posterurlpreview: str | None
    short_description: str | None
    description: str | None
    genres: list[str]
    countries: list[str]
    directors: list[str]


@dataclass(frozen=True)
class MediaCard(MediaSummary):
    votes: int | None
    duration: int | None
    type: str | None
    age_rating: str | None
    rating_mpaa: str | None
    budget_value: Any
    fees_world: Any
    trailer: Any
    top250: int | None
    actors: list[str]
    relations: list[dict]
    similar: list[dict]
    facts: list[dict]


_SUMMARY = load_query("media/bot_summary.sql")
_DETAILS = load_query("media/bot_details.sql")


class MediaRepository:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def search(self, phrase: str) -> list[MediaSummary]:
        words = phrase.replace(",", " ").split()
        if not words:
            return []
        patterns = ["%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" for word in words]
        query = """
            WITH matches AS MATERIALIZED (
                SELECT m.* FROM kinopoisk.media m
                WHERE m.title ILIKE ANY(CAST(:patterns AS text[]))
                   OR m.en_title ILIKE ANY(CAST(:patterns AS text[]))
                   OR m.media_id IN (SELECT a.media_id FROM kinopoisk.media_alias a WHERE a.name ILIKE ANY(CAST(:patterns AS text[])))
                ORDER BY m.votes DESC NULLS LAST, m.media_id LIMIT 50
            )
            SELECT """ + _SUMMARY + " FROM matches m ORDER BY m.votes DESC NULLS LAST, m.media_id"
        async with self.engine.connect() as conn:
            rows = await conn.execute(text(query), {"patterns": patterns})
            return [MediaSummary(**row) for row in rows.mappings()]

    async def card(self, media_id: int) -> MediaCard | None:
        if not 0 < media_id <= 2147483647:
            return None
        return await self._card("SELECT * FROM kinopoisk.media WHERE media_id=:id", {"id": media_id})

    async def random(self) -> MediaCard | None:
        return await self._card("""
            SELECT * FROM kinopoisk.media WHERE rating>=7 AND votes>=50000 ORDER BY random() LIMIT 1
        """, {})

    async def _card(self, selection: str, params: dict) -> MediaCard | None:
        query = f"WITH selected AS ({selection}) SELECT {_SUMMARY}, {_DETAILS} FROM selected m"
        async with self.engine.connect() as conn:
            row = (await conn.execute(text(query), params)).mappings().one_or_none()
            return MediaCard(**row) if row is not None else None
