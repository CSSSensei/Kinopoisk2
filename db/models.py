from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Film(Base):
    __tablename__ = 'films_db'

    id = Column(Integer, primary_key=True, index=True)
    ru_name = Column(String)
    rating_kp = Column(Float)
    votes_kp = Column(Integer)
    genres = Column(Text)
    rating_imdb = Column(Float)
    votes_imdb = Column(Integer)
    imdb = Column(String)
    kphd = Column(String)
    alternativeName = Column(String)
    en_name = Column(String)
    type = Column(String)
    year = Column(Integer)
    movieLength = Column(Integer)
    ratingMpaa = Column(String)
    ageRating = Column(Integer)
    countries = Column(String)
    budget_value = Column(String)
    fees_world = Column(String)
    top10 = Column(Integer)
    top250 = Column(Integer)
    productionCompanies = Column(Text)
    trailer = Column(String)
    similarMovies = Column(Text)
    sequelsAndPrequels = Column(Text)
    actors = Column(Text)
    director = Column(String)
    description = Column(Text)
    shortDescription = Column(Text)
    formula = Column(Float)
    facts = Column(Text)


class UserRecord(Base):
    __tablename__ = 'telegram_users'

    user_id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(Text)
    first_name = Column(Text)
    last_name = Column(Text)
    is_admin = Column(Boolean, nullable=False, server_default='false')
    registration_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QueryRecord(Base):
    __tablename__ = 'telegram_queries'

    query_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('telegram_users.user_id', ondelete='CASCADE'), nullable=False)
    query_text = Column(Text, nullable=False)
    query_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index('ix_telegram_queries_user_date', 'user_id', 'query_date'),)
