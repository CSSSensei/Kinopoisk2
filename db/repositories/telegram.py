from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from db.models import QueryRecord, UserRecord
from db.repositories.models import User


class TelegramRepository:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def register(self, user: User, query: str | None):
        statement = insert(UserRecord).values(user_id=user.user_id, username=user.username,
                                               first_name=user.first_name, last_name=user.last_name)
        async with self.engine.begin() as conn:
            await conn.execute(statement.on_conflict_do_update(
                index_elements=[UserRecord.user_id],
                set_={key: getattr(statement.excluded, key) for key in ("username", "first_name", "last_name")}))
            if query is not None:
                await conn.execute(insert(QueryRecord).values(user_id=user.user_id, query_text=query))

    async def is_admin(self, user_id: int) -> bool:
        async with self.engine.connect() as conn:
            return bool(await conn.scalar(select(UserRecord.is_admin).where(UserRecord.user_id == user_id)))

    async def grant_admin(self, user_id: int):
        async with self.engine.begin() as conn:
            await conn.execute(update(UserRecord).where(UserRecord.user_id == user_id).values(is_admin=True))

    async def users(self, offset: int, limit: int):
        statement = select(UserRecord.__table__, func.count(QueryRecord.query_id).label("queries")).outerjoin(
            QueryRecord, UserRecord.user_id == QueryRecord.user_id).group_by(UserRecord.user_id).order_by(
            UserRecord.registration_date.desc(), UserRecord.user_id.desc()).offset(offset).limit(limit)
        async with self.engine.connect() as conn:
            total = await conn.scalar(select(func.count()).select_from(UserRecord))
            return total, (await conn.execute(statement)).mappings().all()

    async def queries(self, offset: int, limit: int, user_id: int | None = None):
        statement = select(QueryRecord.query_text, QueryRecord.query_date, QueryRecord.user_id,
                           UserRecord.username).join(UserRecord)
        if user_id is not None:
            statement = statement.where(QueryRecord.user_id == user_id)
        statement = statement.order_by(QueryRecord.query_date.desc(), QueryRecord.query_id.desc())
        async with self.engine.connect() as conn:
            return (await conn.execute(statement.offset(offset).limit(limit))).mappings().all()
