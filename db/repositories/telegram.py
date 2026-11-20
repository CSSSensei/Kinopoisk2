from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from db.models import QueryRecord, UserRecord


class TelegramRepository:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def register(self, user: UserRecord, query: str | None) -> bool:
        statement = insert(UserRecord).values(
            user_id=user.user_id, username=user.username, first_name=user.first_name, last_name=user.last_name,
        )
        async with self.engine.begin() as conn:
            upsert = statement.on_conflict_do_update(
                index_elements=[UserRecord.user_id],
                set_={key: getattr(statement.excluded, key) for key in ("username", "first_name", "last_name")})
            banned = await conn.scalar(upsert.returning(UserRecord.is_banned))
            if query is not None and not banned:
                await conn.execute(insert(QueryRecord).values(user_id=user.user_id, query_text=query))

            return banned

    async def get_user(self, user_id: int):
        async with self.engine.connect() as conn:
            result = await conn.execute(select(UserRecord.__table__).where(UserRecord.user_id == user_id))
            return result.mappings().one_or_none()

    async def is_admin(self, user_id: int) -> bool:
        async with self.engine.connect() as conn:
            return bool(await conn.scalar(select(UserRecord.is_admin).where(UserRecord.user_id == user_id)))

    async def set_admin(self, user_id: int, enabled: bool):
        async with self.engine.begin() as conn:
            await conn.execute(update(UserRecord).where(UserRecord.user_id == user_id).values(is_admin=enabled))

    async def set_banned(self, user_id: int, banned: bool):
        async with self.engine.begin() as conn:
            await conn.execute(update(UserRecord).where(UserRecord.user_id == user_id).values(is_banned=banned))

    async def count_queries(self, user_id: int) -> int:
        async with self.engine.connect() as conn:
            return await conn.scalar(select(func.count()).select_from(QueryRecord).where(QueryRecord.user_id == user_id))

    async def users(self, offset: int, limit: int):
        statement = select(UserRecord.__table__, func.count(QueryRecord.query_id).label("queries")).outerjoin(
            QueryRecord, UserRecord.user_id == QueryRecord.user_id).group_by(UserRecord.user_id).order_by(
            UserRecord.registration_date.desc(), UserRecord.user_id.desc()).offset(offset).limit(limit)
        async with self.engine.connect() as conn:
            total = await conn.scalar(select(func.count()).select_from(UserRecord))
            return total, (await conn.execute(statement)).mappings().all()

    async def queries(self, offset: int, limit: int, user_id: int | None = None):
        statement = select(QueryRecord.query_text, QueryRecord.query_date, QueryRecord.user_id,
                           UserRecord.username, UserRecord.first_name, UserRecord.last_name).join(UserRecord)
        if user_id is not None:
            statement = statement.where(QueryRecord.user_id == user_id)
        statement = statement.order_by(QueryRecord.query_date.desc(), QueryRecord.query_id.desc())
        async with self.engine.connect() as conn:
            return (await conn.execute(statement.offset(offset).limit(limit))).mappings().all()
