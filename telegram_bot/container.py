from collections.abc import AsyncIterator

from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from db.repositories.media import MediaRepository
from db.repositories.telegram import TelegramRepository
from telegram_bot.config import BotConfig


class BotProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(self, settings: BotConfig) -> AsyncIterator[AsyncEngine]:
        url = make_url(settings.database_url)
        if url.get_backend_name() not in {"postgres", "postgresql"}:
            raise ValueError("DATABASE_URL must use PostgreSQL")
        options = dict(url.query)
        if "sslmode" in options:
            options["ssl"] = options.pop("sslmode")
        engine = create_async_engine(url.set(drivername="postgresql+asyncpg", query=options), pool_pre_ping=True)
        try:
            yield engine
        finally:
            await engine.dispose()

    catalog = provide(MediaRepository)
    users = provide(TelegramRepository)


def build_container(settings: BotConfig):
    config = Provider(scope=Scope.APP)
    config.provide(lambda: settings, provides=BotConfig)
    return make_async_container(config, BotProvider())
