import os
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


@dataclass
class TgBot:
    token: str
    message_max_symbols: int = 1024


@dataclass
class Config:
    tg_bot: TgBot
    database_url: str
    db_type: str  # 'sqlite' or 'postgres'


def load_config() -> Config:
    return Config(
        tg_bot=TgBot(token=os.getenv('BOT_TOKEN')),
        database_url=os.getenv('DATABASE_URL'),
        db_type=os.getenv('DB_TYPE', 'postgres')  # По умолчанию SQLite, если не указано
    )
