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


def load_config() -> Config:
    return Config(tg_bot=TgBot(token=os.getenv('BOT_TOKEN')))
