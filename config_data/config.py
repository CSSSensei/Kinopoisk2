import os
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


@dataclass
class TgBot:
    token: str
    message_max_symbols: int = 400


@dataclass
class Config:
    tg_bot: TgBot
    database_url: str


def load_config() -> Config:
    return Config(
        tg_bot=TgBot(token=os.getenv('BOT_TOKEN')),
        database_url=os.getenv('DATABASE_URL'),
    )


config: Config = load_config()
