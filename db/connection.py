import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from db.models import Base


def create_postgres_engine(database_url):
    if not database_url:
        raise ValueError("DATABASE_URL is required")
    url = make_url(database_url)
    if url.get_backend_name() not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use PostgreSQL")
    return create_engine(url.set(drivername="postgresql+psycopg2"), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_engine():
    database_url = os.getenv('DATABASE_URL')
    if database_url is None:
        database_url = dotenv_values(Path(__file__).resolve().parents[1] / '.env').get('DATABASE_URL')
    return create_postgres_engine(database_url)


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def initialize_database():
    Base.metadata.create_all(get_engine())


def close_database():
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
