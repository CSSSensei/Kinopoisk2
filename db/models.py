from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Text, func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class UserRecord(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'telegram'}

    user_id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(Text)
    first_name = Column(Text)
    last_name = Column(Text)
    is_admin = Column(Boolean, nullable=False, server_default='false')
    is_banned = Column(Boolean, nullable=False, server_default='false')
    registration_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QueryRecord(Base):
    __tablename__ = 'queries'

    query_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('telegram.users.user_id', ondelete='CASCADE'), nullable=False)
    query_text = Column(Text, nullable=False)
    query_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index('ix_telegram_queries_user_date', 'user_id', 'query_date'), {'schema': 'telegram'})
