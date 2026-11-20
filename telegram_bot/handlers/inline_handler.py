from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.utils.formatting import Text

from db.repositories.media import MediaRepository
from telegram_bot.presenters import pages, summary, web_url


async def inline(query: InlineQuery, catalog: MediaRepository):
    results = []
    for movie in await catalog.search(query.query):
        description = movie.short_description or movie.description or ""
        page = pages(Text(summary(movie), "\n\n", description), 4096)[0]
        results.append(InlineQueryResultArticle(
            id=str(movie.media_id), title=f"{movie.title} | {movie.release_year or '—'}",
            thumbnail_url=web_url(movie.posterurlpreview) or web_url(movie.posterurl),
            input_message_content=InputTextMessageContent(message_text=page.text, entities=page.entities,
                                                         parse_mode=None),
            description=f"{movie.rating if movie.rating is not None else '—'} | {description}",
        ))
    await query.answer(results, cache_time=1, is_personal=True)


def router():
    result = Router(name="inline")
    result.inline_query.register(inline)
    return result
