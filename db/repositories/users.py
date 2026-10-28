from datetime import datetime
from typing import Iterator, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert

from config_data.models import Query, User
from db.connection import get_session_factory
from db.models import QueryRecord, UserRecord


class UserRepository:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    @staticmethod
    def _local_time(value: Optional[datetime]):
        return value.astimezone(ZoneInfo('Europe/Moscow')) if value else None

    @classmethod
    def _user(cls, record):
        if record is None:
            return None
        return User(
            user_id=record.user_id, username=record.username,
            first_name=record.first_name, last_name=record.last_name,
            is_admin=record.is_admin, registration_date=cls._local_time(record.registration_date),
        )

    @classmethod
    def _query(cls, record, user):
        return Query(
            query_id=record.query_id, user_id=record.user_id,
            query_text=record.query_text, query_date=cls._local_time(record.query_date),
            user=cls._user(user),
        )

    def add_user(self, user: User) -> User:
        statement = insert(UserRecord).values(
            user_id=user.user_id, username=user.username, first_name=user.first_name,
            last_name=user.last_name, is_admin=user.is_admin,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[UserRecord.user_id],
            set_={name: getattr(statement.excluded, name) for name in ('username', 'first_name', 'last_name')},
        ).returning(UserRecord)
        with self.session_factory.begin() as session:
            return self._user(session.execute(statement).scalar_one())

    def get_user(self, user_id: int) -> Optional[User]:
        with self.session_factory() as session:
            return self._user(session.get(UserRecord, user_id))

    def update_user(self, user: User) -> Optional[User]:
        statement = update(UserRecord).where(UserRecord.user_id == user.user_id).values(
            username=user.username, first_name=user.first_name,
            last_name=user.last_name, is_admin=user.is_admin,
        ).returning(UserRecord)
        with self.session_factory.begin() as session:
            return self._user(session.execute(statement).scalar_one_or_none())

    def delete_user(self, user_id: int) -> bool:
        with self.session_factory.begin() as session:
            return session.execute(delete(UserRecord).where(UserRecord.user_id == user_id)).rowcount > 0

    def get_all_users(self) -> Iterator[User]:
        statement = select(UserRecord).order_by(UserRecord.registration_date.desc(), UserRecord.user_id.desc())
        with self.session_factory() as session:
            users = [self._user(record) for record in session.scalars(statement)]
        return iter(users)

    def get_admins(self) -> Iterator[User]:
        with self.session_factory() as session:
            admins = [self._user(record) for record in session.scalars(
                select(UserRecord).where(UserRecord.is_admin.is_(True)).order_by(UserRecord.user_id)
            )]
        return iter(admins)

    def set_admin(self, user_id: int, is_admin: bool = True) -> bool:
        with self.session_factory.begin() as session:
            return session.execute(update(UserRecord).where(UserRecord.user_id == user_id).values(is_admin=is_admin)).rowcount > 0

    def add_query(self, query: Query) -> Query:
        with self.session_factory.begin() as session:
            record = QueryRecord(user_id=query.user_id, query_text=query.query_text)
            session.add(record)
            session.flush()
            return self._query(record, session.get(UserRecord, query.user_id))

    def _queries(self, *, user_id=None, query_id=None, limit=None) -> List[Query]:
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
            raise ValueError('limit must be a nonnegative integer')
        statement = select(QueryRecord, UserRecord).outerjoin(UserRecord).order_by(
            QueryRecord.query_date.desc(), QueryRecord.query_id.desc()
        )
        if user_id is not None:
            statement = statement.where(QueryRecord.user_id == user_id)
        if query_id is not None:
            statement = statement.where(QueryRecord.query_id == query_id)
        if limit is not None:
            statement = statement.limit(limit)
        with self.session_factory() as session:
            return [self._query(record, user) for record, user in session.execute(statement)]

    def get_query(self, query_id: int) -> Optional[Query]:
        queries = self._queries(query_id=query_id, limit=1)
        return queries[0] if queries else None

    def get_last_queries(self, amount: int = 10) -> List[Query]:
        return self._queries(limit=amount)

    def get_user_queries(self, user_id: int, limit: Optional[int] = None) -> Iterator[Query]:
        return iter(self._queries(user_id=user_id, limit=limit))

    def get_all_queries(self, limit: Optional[int] = None) -> Iterator[Query]:
        return iter(self._queries(limit=limit))

    def delete_query(self, query_id: int) -> bool:
        with self.session_factory.begin() as session:
            return session.execute(delete(QueryRecord).where(QueryRecord.query_id == query_id)).rowcount > 0

    def delete_user_queries(self, user_id: int) -> int:
        with self.session_factory.begin() as session:
            return session.execute(delete(QueryRecord).where(QueryRecord.user_id == user_id)).rowcount
