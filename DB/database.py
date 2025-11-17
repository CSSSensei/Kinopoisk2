from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config_data.config import load_config
from query_loader import load_query

config = load_config()
DATABASE_URL = config.database_url

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine)


async def execute_query(query_path: str, params: dict = None):
    async with SessionLocal() as session:
        sql = load_query(query_path)
        result = await session.execute(text(sql), params or {})
        return result
